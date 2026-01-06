{
    'name': 'Simple Approval Line',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Simple approval workflow for any module',
    'description': """
        Simple Approval Line Module
        ============================
        Approval workflow yang bisa digunakan di modul manapun:
        - Sales Order
        - Purchase Order
        - HR Leave
        - Account Move
        - Dan lainnya
    """,
    'depends': ['base', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/approval_line_action_menu.xml',
        'views/approval_line_list_view.xml',
        'views/approval_line_form_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}