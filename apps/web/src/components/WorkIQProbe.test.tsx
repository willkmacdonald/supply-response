// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {cleanup, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
import {setAccessTokenProvider} from "../api";
import {WorkIQProbe} from "./WorkIQProbe";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); setAccessTokenProvider(async () => null); });

it("does not run until clicked and invokes one authenticated bodyless POST", async () => {
  setAccessTokenProvider(async () => "api-secret");
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
    stage: "complete", http_status: 200, authenticated_alex: true, obo_succeeded: true,
    mcp_initialized: true, fetch_succeeded: true, exact_message_identity: true,
    expected_author: true, valid_source_timestamp: true, nonempty_body: true,
    expected_channel_identity: true, expected_source_link: true,
  }), {status: 200, headers: {"Content-Type": "application/json"}}));
  vi.stubGlobal("fetch", fetchMock);
  render(<WorkIQProbe />);
  expect(fetchMock).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", {name: "Run diagnostic once"}));
  expect(await screen.findByText("Stage: complete")).toBeVisible();
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock).toHaveBeenCalledWith("/api/diagnostics/workiq-fetch", {
    method: "POST", headers: {Authorization: "Bearer api-secret"},
  });
  expect(screen.getByRole("button")).toBeDisabled();
});

it("uses fixed error copy without exposing server content", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("sensitive upstream value")));
  render(<WorkIQProbe />);
  await userEvent.click(screen.getByRole("button"));
  expect(await screen.findByRole("alert")).toHaveTextContent("The diagnostic could not be completed.");
  expect(screen.queryByText(/sensitive/)).not.toBeInTheDocument();
});
