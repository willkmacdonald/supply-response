// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {useState} from "react";
import {afterEach, describe, expect, it, vi} from "vitest";
import type {SupplierEmailState} from "../types";
import {SupplierEmailPanel} from "./SupplierEmailPanel";

const initialEmail: SupplierEmailState = {
  email_id: "email-1",
  decision_id: "decision-1",
  action_id: "action-1",
  revision: 1,
  subject: "RL-001 supplier recovery request",
  body: "Please confirm the current recovery timing.",
  from_address: "agent@willmacdonald.com",
  to_address: "will@willmacdonald.com",
  reviewed_revision: null,
  reviewed_at: null,
  reviewed_by: null,
  send_status: "draft",
};

afterEach(cleanup);

describe("SupplierEmailPanel", () => {
  it("requires each edited revision to be saved and reviewed before Send is enabled", async () => {
    const user = userEvent.setup();
    const save = vi.fn();
    const review = vi.fn();

    function Harness() {
      const [email, setEmail] = useState(initialEmail);
      return <SupplierEmailPanel email={email} busy={false} sendEnabled
        onSave={async input => {
          save(input);
          const next = {...email, ...input, revision: email.revision + 1, reviewed_revision: null,
            reviewed_at: null, reviewed_by: null};
          setEmail(next);
          return next;
        }}
        onReview={async revision => {
          review(revision);
          const next = {...email, reviewed_revision: revision, reviewed_at: "2026-09-15T12:00:00Z",
            reviewed_by: {persona_id: "RL-PERSONA-ALEX"} as never};
          setEmail(next);
          return next;
        }}
        onSend={vi.fn()} onCheckStatus={vi.fn()} />;
    }

    render(<Harness />);

    expect(screen.getByText("From: Alex — agent@willmacdonald.com")).toBeVisible();
    expect(screen.getByText("To: Supplier Alpha (demo) — will@willmacdonald.com")).toBeVisible();
    expect(screen.getByLabelText("Subject")).toHaveValue(initialEmail.subject);
    expect(screen.getByLabelText("Message")).toHaveValue(initialEmail.body);
    expect(screen.getByText("Not sent")).toBeVisible();
    expect(screen.getByRole("button", {name: "Review this email"})).toBeEnabled();
    expect(screen.getByRole("button", {name: "Send email"})).toBeDisabled();

    await user.type(screen.getByLabelText("Subject"), " — revised");
    expect(screen.getByRole("button", {name: "Save changes"})).toBeEnabled();
    expect(screen.getByRole("button", {name: "Send email"})).toBeDisabled();
    await user.click(screen.getByRole("button", {name: "Save changes"}));
    expect(save).toHaveBeenCalledWith({
      revision: 1,
      subject: "RL-001 supplier recovery request — revised",
      body: initialEmail.body,
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Changes saved. Review this email before sending.");

    await user.click(screen.getByRole("button", {name: "Review this email"}));
    expect(review).toHaveBeenCalledWith(2);
    expect(await screen.findByRole("button", {name: "Send email"})).toBeEnabled();
    expect(screen.getByRole("status")).toHaveTextContent("Email reviewed. It is ready to send.");

    await user.type(screen.getByLabelText("Message"), " New constraint.");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("button", {name: "Save changes"})).toBeEnabled();
    expect(screen.getByRole("button", {name: "Send email"})).toBeDisabled();
    await user.click(screen.getByRole("button", {name: "Save changes"}));
    expect(screen.getByRole("button", {name: "Review this email"})).toBeEnabled();
    expect(screen.getByRole("button", {name: "Send email"})).toBeDisabled();
  });

  it("shows Sending immediately and ignores a second send click", async () => {
    const user = userEvent.setup();
    let finishSend!: (email: SupplierEmailState) => void;
    const onSend = vi.fn(() => new Promise<SupplierEmailState>(resolve => { finishSend = resolve; }));
    const reviewed = {...initialEmail, reviewed_revision: 1, reviewed_at: "2026-09-15T12:00:00Z",
      reviewed_by: {persona_id: "RL-PERSONA-ALEX"} as never};

    render(<SupplierEmailPanel email={reviewed} busy={false} sendEnabled onSave={vi.fn()} onReview={vi.fn()}
      onSend={onSend} onCheckStatus={vi.fn(() => new Promise<SupplierEmailState>(() => undefined))} />);

    const send = screen.getByRole("button", {name: "Send email"});
    await user.click(send);
    expect(screen.getByRole("button", {name: "Sending…"})).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Sending…");
    await user.click(screen.getByRole("button", {name: "Sending…"}));
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith(1);

    finishSend({...reviewed, send_status: "accepted"});
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Accepted by Microsoft 365"));
  });

  it("reconciles an accepted submission once while keeping its accepted feedback visible", async () => {
    let finishCheck!: (email: SupplierEmailState) => void;
    const onCheckStatus = vi.fn(() => new Promise<SupplierEmailState>(resolve => { finishCheck = resolve; }));
    const accepted = {...initialEmail, reviewed_revision: 1, reviewed_at: "2026-09-15T12:00:00Z",
      reviewed_by: {persona_id: "RL-PERSONA-ALEX"} as never, send_status: "accepted" as const};

    render(<SupplierEmailPanel email={accepted} busy={false} sendEnabled onSave={vi.fn()} onReview={vi.fn()}
      onSend={vi.fn()} onCheckStatus={onCheckStatus} />);

    expect(screen.getByText("Accepted by Microsoft 365")).toBeVisible();
    await waitFor(() => expect(onCheckStatus).toHaveBeenCalledTimes(1));
    expect(screen.getByText("Accepted by Microsoft 365")).toBeVisible();
    expect(screen.queryByRole("button", {name: "Check send status"})).not.toBeInTheDocument();

    finishCheck({...accepted, send_status: "sent-confirmed"});
    expect(await screen.findByRole("status")).toHaveTextContent("Sent");
    expect(onCheckStatus).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["accepted", "Accepted by Microsoft 365"],
    ["sent-confirmed", "Sent"],
    ["failed", "Send failed"],
    ["uncertain", "Send status uncertain"],
  ] as const)("maps %s to the proven status %s without claiming delivery", (send_status, label) => {
    render(<SupplierEmailPanel email={{...initialEmail, send_status}} busy={false} sendEnabled
      onSave={vi.fn()} onReview={vi.fn()} onSend={vi.fn()}
      onCheckStatus={send_status === "accepted" ? vi.fn(() => new Promise<SupplierEmailState>(() => undefined)) : vi.fn()} />);

    expect(screen.getByText(label)).toBeVisible();
    expect(screen.queryByText(/Delivered/i)).not.toBeInTheDocument();
    if (send_status === "uncertain") {
      expect(screen.getByRole("button", {name: "Check send status"})).toBeEnabled();
    } else {
      expect(screen.queryByRole("button", {name: "Check send status"})).not.toBeInTheDocument();
    }
  });

  it("disables Send and explains when the environment cannot send email", () => {
    const reviewed = {...initialEmail, reviewed_revision: 1, reviewed_at: "2026-09-15T12:00:00Z",
      reviewed_by: {persona_id: "RL-PERSONA-ALEX"} as never};

    render(<SupplierEmailPanel email={reviewed} busy={false} sendEnabled={false}
      onSave={vi.fn()} onReview={vi.fn()} onSend={vi.fn()} onCheckStatus={vi.fn()} />);

    expect(screen.getByRole("button", {name: "Send email"})).toBeDisabled();
    expect(screen.getByText("Email sending is not enabled for this demo environment.")).toBeVisible();
  });
});
