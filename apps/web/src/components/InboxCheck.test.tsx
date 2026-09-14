// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {act, cleanup, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
import {ApiRequestError, api} from "../api";
import {InboxCheck} from "./InboxCheck";
afterEach(() => {cleanup(); vi.restoreAllMocks();});
const result = {checked_at:"2026-09-14T05:00:00Z",incomplete:false,messages:[{
 message_id:"new-message",subject:"[Supply Response Demo] RL-001 | Supplier Alpha | Run A",
 sender:"will@willmacdonald.com",received_at:"2026-09-14T04:59:00Z",
 excerpt:"RL-MAT-10247 shipment is delayed.",citation_url:"https://outlook.office365.com/mail/deeplink/read/new-message",
}]};
it("checks only on click and shows the actual message and Outlook citation", async () => {
 const check=vi.spyOn(api,"checkInbox").mockResolvedValue(result);
 const create=vi.spyOn(api,"createCase");
 render(<InboxCheck/>);
 expect(check).not.toHaveBeenCalled();
 await userEvent.click(screen.getByRole("button",{name:"Check email for disruptions"}));
 expect(check).toHaveBeenCalledTimes(1);
 expect(await screen.findByText(result.messages[0].subject)).toBeVisible();
 expect(screen.getByRole("link",{name:"Open supplier email"})).toHaveAttribute("href",result.messages[0].citation_url);
 await userEvent.click(screen.getByText("Review disruption"));
 expect(screen.getByText(result.messages[0].excerpt)).toBeVisible();
 expect(create).not.toHaveBeenCalled();
});
const reviewable = {...result, messages: [{...result.messages[0],
 internet_message_id: "<run-a@example.com>", review_fingerprint: "a".repeat(64), creation_blocker: null,
 facts: {original_quantity:8000,part_id:"RL-MAT-10247",plant_name:"Chicago",original_due_date:"2026-09-03",
 partial_quantity:3000,partial_due_date:"2026-09-06",additional_cost_per_unit:"7.50",remaining_quantity:5000,recovery_date:null},
}]};
it("reviews extracted facts before explicitly creating, immediately shows progress, and opens the returned case", async () => {
 vi.spyOn(api,"checkInbox").mockResolvedValue(reviewable);
 let resolve!: (value: Awaited<ReturnType<typeof api.createCaseFromEmail>>)=>void;
 const create=vi.spyOn(api,"createCaseFromEmail").mockReturnValue(new Promise(done=>{resolve=done;}));
 const opened=vi.fn(); const busy=vi.fn();
 render(<InboxCheck onCaseCreated={opened} onBusyChange={busy}/>);
 await userEvent.click(screen.getByRole("button",{name:"Check email for disruptions"}));
 await userEvent.click(await screen.findByText("Review disruption"));
 expect(screen.getByText(/8,000 units.*RL-MAT-10247.*Chicago/)).toBeVisible();
 expect(screen.getByText(/\$7\.50 per component unit/)).toBeVisible();
 expect(screen.getByText(/5,000 units.*no confirmed delivery date/)).toBeVisible();
 expect(create).not.toHaveBeenCalled();
 const button=screen.getByRole("button",{name:"Create case from this email"});
 await userEvent.dblClick(button);
 expect(create).toHaveBeenCalledTimes(1);
 expect(create).toHaveBeenCalledWith("<run-a@example.com>", "a".repeat(64));
 expect(screen.getByRole("button",{name:"Creating disruption case…"})).toBeDisabled();
 expect(screen.getByRole("button",{name:"Check email for disruptions"})).toBeDisabled();
 expect(busy).toHaveBeenLastCalledWith(true);
 await act(async()=>resolve({case_id:"created-email-case",template_id:"RL-001",purpose:"showcase",runtime_mode:"live",
  status:"open",scenario_effective_time:"2026-09-01T09:00:00-05:00",scenario_timezone:"America/Chicago",current_analysis_id:null,current_decision_id:null,
  display_status:null,recorded_at:"2026-09-14T05:00:00Z",projection_updated_at:"2026-09-14T05:00:00Z",
  controls:{new_analysis:true,decide:false,retry_action_planning:false,start_playback:false}}));
 expect(opened).toHaveBeenCalledWith("created-email-case");
 expect(busy).toHaveBeenLastCalledWith(false);
});
it("keeps the review after a failed create and gives a useful changed-email error", async () => {
 vi.spyOn(api,"checkInbox").mockResolvedValue(reviewable);
 const create=vi.spyOn(api,"createCaseFromEmail").mockRejectedValue(new ApiRequestError("raw secret",409,"INBOUND_EMAIL_CHANGED"));
 render(<InboxCheck onCaseCreated={vi.fn()}/>);
 await userEvent.click(screen.getByRole("button",{name:"Check email for disruptions"}));
 await userEvent.click(await screen.findByText("Review disruption"));
 await userEvent.click(screen.getByRole("button",{name:"Create case from this email"}));
 expect(await screen.findByRole("alert")).toHaveTextContent(/email changed.*check email again/i);
 expect(screen.getByText(result.messages[0].excerpt)).toBeVisible();
 expect(screen.getByRole("button",{name:"Create case from this email"})).toBeEnabled();
 expect(create).toHaveBeenCalledTimes(1);
});
it("shows an unsupported-message explanation without enabling creation", async () => {
 vi.spyOn(api,"checkInbox").mockResolvedValue({...reviewable,messages:[{...reviewable.messages[0],facts:null,creation_blocker:"The partial shipment date is missing."}]});
 const create=vi.spyOn(api,"createCaseFromEmail");
 render(<InboxCheck onCaseCreated={vi.fn()}/>);
 await userEvent.click(screen.getByRole("button",{name:"Check email for disruptions"}));
 await userEvent.click(await screen.findByText("Review disruption"));
 expect(screen.getByText("The partial shipment date is missing.")).toBeVisible();
 expect(screen.queryByRole("button",{name:"Create case from this email"})).not.toBeInTheDocument();
 expect(create).not.toHaveBeenCalled();
});
it("locks the check while pending and distinguishes incomplete from empty results", async () => {
 let resolve!: (value: typeof result)=>void;
 vi.spyOn(api,"checkInbox").mockReturnValue(new Promise(done=>{resolve=done;}));
 const busy=vi.fn(); render(<InboxCheck onBusyChange={busy}/>);
 await userEvent.click(screen.getByRole("button",{name:"Check email for disruptions"}));
 expect(screen.getByRole("button",{name:"Checking email…"})).toBeDisabled();
 expect(busy).toHaveBeenCalledWith(true);
 await act(async()=>resolve({...result,incomplete:true,messages:[]}));
 expect(await screen.findByText(/could not check every matching email/i)).toBeVisible();
 expect(screen.queryByText("No matching supplier emails found.")).not.toBeInTheDocument();
 expect(busy).toHaveBeenLastCalledWith(false);
});
it("shows an empty result and allows retry after a safe error without retaining old results", async () => {
 vi.spyOn(api,"checkInbox").mockResolvedValueOnce(result).mockRejectedValueOnce(new Error("secret body"))
  .mockResolvedValueOnce({...result,messages:[]});
 render(<InboxCheck/>);
 const check=screen.getByRole("button",{name:"Check email for disruptions"});
 await userEvent.click(check); await screen.findByText(result.messages[0].subject);
 await userEvent.click(check);
 expect(await screen.findByRole("alert")).not.toHaveTextContent("secret body");
 expect(screen.queryByText(result.messages[0].subject)).not.toBeInTheDocument();
 await userEvent.click(check);
 expect(await screen.findByText("No matching supplier emails found.")).toBeVisible();
});
