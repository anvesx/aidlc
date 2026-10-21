---
disable-model-invocation: true
description: Approve the AIDLC step that is waiting for your decision (or a proposed go-back). Only you can approve; Claude never does.
argument-hint: "[part of the file path, if more than one step is waiting]"
---

The person typed `/aidlc:approve $ARGUMENTS`. The AIDLC approve hook has already handled it and added a message starting with "AIDLC approve:" to this conversation.

- If that message says something was approved: tell the person in one line, and that the driver will pick it up and continue (if no driver is running for this work, `/aidlc:start` gives the command to start one). Then stop. **Do not continue with the next step yourself**; only the driver continues.
- If it says nothing was waiting, several things were waiting, the approver isn't allowed, or something went wrong: tell the person exactly what it says.
- If there is no "AIDLC approve:" message, the hook did not run. Tell the person approval was **not** recorded and that the AIDLC plugin's hooks must be on.

Never write an approval yourself.
