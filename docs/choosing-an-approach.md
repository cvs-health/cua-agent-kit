# Choosing an approach

Start with the workflow you want to automate and what its UI exposes.

| Approach       | Use it when                                                          | What runs repeatedly                                   |
| -------------- | -------------------------------------------------------------------- | ------------------------------------------------------ |
| Browser        | Playwright can access the website's DOM                              | Codified Playwright code                               |
| Native Windows | The app exposes usable UI Automation or Win32 controls               | Codified pywinauto code on the Windows host            |
| AI-driven      | You want visual automation, or reliable controls are unavailable     | An agent observing screenshots and choosing actions    |
| Hybrid         | Most steps are predictable, but some need interpretation or judgment | Deterministic steps with explicit model-assisted steps |

## Browser or native Windows

Use AI discovery to demonstrate the workflow, then codify successful runs into
ordinary code with selectors, waits, and outcome checks. Repeat execution does
not need a model API key.

For example, use Playwright for website forms and pywinauto for a Windows app's
fields, buttons, and dialogs. Check representative screens: an accessible main
window does not guarantee accessible controls everywhere.

## AI-driven, without codification

You can keep using the agent directly. Codification is not required.

For some apps, such as a Citrix-delivered app exposing only its rendered image,
the local Windows desktop may have no accessible controls for the app's actual
fields and buttons. An AI-driven workflow can operate from screenshots instead.
Not every Citrix app has the same accessibility; choose based on what is
exposed.

This uses model calls each run, with their associated cost and variability. The
kit's Windows discovery command also serves this AI-driven mode:
`uv run cua-agent-discover` with `DISCOVERY_BACKEND=windows`.

## Hybrid

Sometimes selectors can handle navigation and data entry, but a step needs an
LLM to interpret a document or make a judgment. Keep the predictable steps in
code and make the model-assisted step explicit, with a defined input and output.

The kit does not currently provide a ready-made hybrid runner or automatically
insert model calls into codified workflows. This is an approach you can build
when your workflow needs it.

## Start here

- [Browser quickstart](../README.md#setup)
- [Windows VM setup](windows-vm-setup.md)
- [Codify browser workflows](../.codex/skills/codify-playwright-workflow/SKILL.md)
- [Codify Windows workflows](../.codex/skills/codify-windows-workflow/SKILL.md)

An agent finishing its run does not prove the task succeeded. Verify the
intended result, whichever approach you choose.
