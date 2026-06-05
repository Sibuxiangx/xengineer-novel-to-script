---
version: 2
name: ScriptWeaver Ant Design X Workspace
source_inspiration: "https://x.ant.design/components/introduce-cn/"
description: "A Chinese-market AI chat workspace built with Ant Design X recommended components."
---

# DESIGN.md

The frontend should follow Ant Design X and Ant Design defaults. Prefer a familiar
Chinese SaaS / AI assistant aesthetic over custom visual experiments.

## Product Shape

- Left pane: `Conversations` for project sessions.
- Center pane: `Welcome`, `Prompts`, `Bubble.List`, `Sender`, and `Attachments`.
- Right pane: persistent asset inspector with Ant Design `Tabs`, `Card`, `Collapse`,
  `Statistic`, `Alert`, and Monaco for YAML.

The first screen is the real product, not a landing page. Users should immediately
see where to upload TXT content and how to start chatting with the agent.

## Design Direction

- Use Ant Design X components whenever a matching component exists.
- Keep Ant Design's clean light theme, blue primary action color, standard cards,
  tags, badges, and spacing.
- Avoid custom dark shells, unusual palettes, decorative gradients, and bespoke
  chat bubbles.
- The product should feel like a polished domestic AI assistant/workbench.

## Component Mapping

- Chat messages: `Bubble.List`
- User input: `Sender`
- TXT upload and paste: `Attachments` inside `Sender.Header`
- Empty state: `Welcome` and `Prompts`
- Project/session list: `Conversations`
- Agent tool calls: `ThoughtChain`
- Confirmation panel: Ant Design `Card`, `Statistic`, `Input.TextArea`, `Tag`, `Button`
- Assets: Ant Design `Tabs`, `Collapse`, `Alert`, `Card`, `Statistic`

## Interaction Rules

- Show tool calls visibly as an execution trace.
- Preserve pending confirmation after refresh.
- Confirming chapter split continues the import, index, YAML generation, validation,
  and version creation flow.
- Keep the right asset panel visible on desktop.
- Do not fake success states. Backend/model errors must be visible.

## Implementation Rules

- Prefer Ant Design X component props and token customization over hand-written
  component shells.
- CSS should be minimal and structural: layout, sizing, and small polish only.
- Keep the interface Chinese-first.
- Avoid adding third-party UI kits unless Ant Design X cannot satisfy the component.
