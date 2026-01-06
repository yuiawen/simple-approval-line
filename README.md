# Simple Approval Line

A lightweight approval module to add multi-level approvals to any Odoo model via a mixin.

## Overview

Main components:

- `approval.line` stores approver lines per document (who, sequence, status, notes).
- `approval.mixin` adds approval state + helper actions to request, approve, reject, and view approval lines.

## Features

- Pluggable into any model via `_inherit` (mixin).
- Multi-level approval via `sequence`.
- Access enforcement: only the assigned approver can approve or reject.
- Basic audit fields: status, approved date, notes.
- Optional chatter logging on the target document (requires `mail.thread` on the target model).

## Suggested structure

```
simple_approval_line/
├─ __manifest__.py
├─ models/
│  ├─ __init__.py
│  ├─ approval_line.py
│  └─ approval_mixin.py
├─ security/
│  └─ ir.model.access.csv
└─ views/
   ├─ approval_line_action_menu.xml
   ├─ approval_line_form_view.xml
   └─ approval_line_list_view.xml
```

## Installation

1. Put `simple_approval_line` inside your addons path.
2. Update the Apps List.
3. Install module: **Simple Approval Line**.

## Using it in another module

### 1) Add dependency

In your target module `__manifest__.py`:

```python
'depends': ['base', 'hr', 'simple_approval_line'],
```

If you want chatter messages on the target document, also depend on `mail` and inherit `mail.thread`.

### 2) Inject the mixin into the target model

Example for Sales Order:

```python
from odoo import models

class SaleOrder(models.Model):
    _inherit = ['sale.order', 'approval.mixin', 'mail.thread', 'mail.activity.mixin']
```

Minimum requirement is `approval.mixin`. Chatter posting only works if `mail.thread` is present.

### 3) Define approvers

Override `_get_approvers()` on the target model.

It must return a **recordset** of `res.users`, in the intended order.

Example 2-level approvers from HR hierarchy (manager, then manager's manager):

```python
def _get_approvers(self):
    approvers = self.env['res.users']
    emp = self.env.user.employee_id
    if emp and emp.parent_id and emp.parent_id.user_id:
        approvers |= emp.parent_id.user_id
        if emp.parent_id.parent_id and emp.parent_id.parent_id.user_id:
            approvers |= emp.parent_id.parent_id.user_id
    return approvers
```

Example by group membership:

```python
def _get_approvers(self):
    group = self.env.ref('base.group_system')
    return group.users
```

### 4) Add buttons to the target form view

Example header snippet:

```xml
<header>
    <field name="approval_state" widget="statusbar"
           statusbar_visible="draft,waiting,approved,rejected"/>

    <button name="action_request_approval" type="object" string="Request Approval"
            class="oe_highlight"
            invisible="approval_state != 'draft'"/>

    <button name="action_approve_line" type="object" string="Approve"
            class="oe_highlight"
            invisible="approval_state != 'waiting' or not is_approver"/>

    <button name="action_reject_line" type="object" string="Reject"
            invisible="approval_state != 'waiting' or not is_approver"/>

    <button name="action_view_approval_lines" type="object" string="Approval Lines"/>
</header>
```

To show line details inside the document form, add a notebook page with `approval_line_ids`.

## Workflow

1. `action_request_approval()`

   - Removes old approval lines for the same document.
   - Gets approvers from `_get_approvers()`.
   - Creates `approval.line` records (sequence 10, 20, 30, ...).
   - Sets `approval_state = waiting`.

2. Approver calls `action_approve_line()` or `action_reject_line()`
   - Enforces that only the assigned approver for a `pending` line can act.
   - When all lines become `approved`, the mixin triggers the final hook.

## Hooks you can override

| Method                     | Required | Purpose                          |
| -------------------------- | -------- | -------------------------------- |
| `_get_approvers()`         | Yes      | Returns approvers (`res.users`)  |
| `_approval_all_approved()` | No       | Runs when all lines are approved |
| `_approval_rejected(line)` | No       | Runs when a line is rejected     |

Default behavior:

- `_approval_all_approved()` sets `approval_state` to `approved` and posts a message (if chatter exists).
- `_approval_rejected(line)` sets `approval_state` to `rejected` and posts a message (if chatter exists).

## Menu

The module provides:

- **Approvals → Approval Lines**

Useful for admins to monitor all approval lines.

## Security

Default ACL for `approval.line`:

- `base.group_user`: read, write, create, no unlink
- `base.group_system`: full access

Approval and rejection rules are enforced in `approval.line` methods (`action_approve()` / `action_reject()`).

## Troubleshooting

- **Error: "No approvers found"**

  - Ensure `_get_approvers()` returns a `res.users` recordset.
  - If using HR hierarchy, ensure `employee.parent_id.user_id` is set.

- **No chatter message on the document**

  - Ensure the target model inherits `mail.thread` and module `mail` is installed.

- **Approver cannot approve**
  - Ensure the logged-in user matches `approver_id` on the `pending` line.
  - Ensure the user has access to the target document.

## Limitations

- This is not a full rules engine.
- Approval ordering strictly follows the recordset order returned by `_get_approvers()`.
