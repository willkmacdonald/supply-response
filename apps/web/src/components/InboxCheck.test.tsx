// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {act, cleanup, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, it, vi} from "vitest";
import {api} from "../api";
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
 await userEvent.click(screen.getByText("Review email"));
 expect(screen.getByText(result.messages[0].excerpt)).toBeVisible();
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
