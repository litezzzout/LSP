from .code_actions import CodeActionOrCommand
from .core.protocol import Diagnostic
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.sessions import SessionBufferProtocol
from .core.typing import List, Optional, Any, Dict, Tuple, Sequence
from .core.views import text_document_identifier
import sublime


SUBLIME_WORD_MASK = 515

class LspSemanticCommand(LspTextCommand):

    capability = 'semanticTokensProvider'

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._base_dir = None   # type: Optional[str]

    def run(
        self,
        edit: sublime.Edit,
        only_diagnostics: bool = False
    ) -> None:

        window = self.view.window()
        if not window:
            return
        wm = windows.lookup(window)
        self._base_dir = wm.get_project_path(self.view.file_name() or "")
        self._actions_by_config = {}  # type: Dict[str, List[CodeActionOrCommand]]
        self._diagnostics_by_config = []  # type: Sequence[Tuple[SessionBufferProtocol, Sequence[Diagnostic]]]

        def run_async() -> None:
            if not only_diagnostics:
                self.request_semantic_tokens_async()

        sublime.set_timeout_async(run_async)

    def request_semantic_tokens_async(self) -> None:
        session = self.best_session(self.capability)
        if session:
            token_types = None
            try:
                token_types = session.get_capability('semanticTokensProvider')['legend']['tokenTypes']
            except:
                # print('semantic highlighting capabilies not provided by the server!!!')
                return

            params = {"textDocument": text_document_identifier(self.view)}
            session.send_request_async(
                Request("textDocument/semanticTokens/full", params, self.view),
                lambda response: self.handle_response(response, token_types))

    def handle_response(self, response: Optional[Any], token_types: list) -> None:
        # print("LSP:RESPONSE:   ", response['data'])

        my_structs     = []
        my_vars        = []
        my_params      = []
        my_fields      = []
        my_macros      = []
        my_enums       = []
        my_enum_fields = []
        my_types       = []
        my_funcs       = []

        data = response['data']
        prev_row = None
        prev_col = None
        for x in range(0, len(data),5):
            things = data[x:x+5]

            if prev_row is not None:
                if things[0] == 0:
                    things[1] += prev_col
                    things[0]  = prev_row
                else:
                    things[0] += prev_row

            point1 = self.view.text_point(things[0], things[1])
            point2 = self.view.text_point(things[0], things[1]+things[2])
            my_region = sublime.Region(point1, point2)

            if token_types[things[3]] ==     'macro': my_macros.append(my_region)
            if token_types[things[3]] ==     'class': my_structs.append(my_region)
            if token_types[things[3]] ==  'property': my_fields.append(my_region)
            if token_types[things[3]] ==  'function': my_funcs.append(my_region)
            if token_types[things[3]] == 'parameter': my_params.append(my_region)
            if token_types[things[3]] ==  'variable': my_vars.append(my_region)
            if token_types[things[3]] ==      'enum': my_enums.append(my_region)
            if token_types[things[3]] =='enumMember': my_enum_fields.append(my_region)
            if token_types[things[3]] ==      'type': my_types.append(my_region)

            prev_row = things[0]
            prev_col = things[1]
        
        self.view.add_regions('semantic_macro',     my_macros,      'semantic_macro',     flags= sublime.DRAW_NO_OUTLINE)
        self.view.add_regions('semantic_var',       my_vars,        'semantic_var',       flags= sublime.DRAW_NO_OUTLINE)
        self.view.add_regions('semantic_param',     my_params,      'semantic_param',     flags= sublime.DRAW_NO_OUTLINE)
        self.view.add_regions('semantic_struct',    my_structs,     'semantic_struct',    flags= sublime.DRAW_NO_OUTLINE)
        self.view.add_regions('semantic_type',      my_types,       'semantic_type',      flags= sublime.DRAW_NO_OUTLINE)
        self.view.add_regions('semantic_enum',      my_enums,       'semantic_enum',      flags= sublime.DRAW_NO_OUTLINE)
        self.view.add_regions('semantic_enumfield', my_enum_fields, 'semantic_enumfield', flags= sublime.DRAW_NO_OUTLINE)
        self.view.add_regions('semantic_field',     my_fields,      'semantic_field',     flags= sublime.DRAW_NO_OUTLINE)
        self.view.add_regions('semantic_func',      my_funcs,       'semantic_func',      flags= sublime.DRAW_NO_OUTLINE)

        '''
        Color Scheme :
        these is what your color scheme should look like to work with semantic highligthing
    
        "variables":
        {
            "background": "#0B0c0f",
            "background1": "#0B0c0e",

            "default": "#569cd6",
            "keyword": "#569cd6",

        
            "function": "#dbdbaa",
            "parameter": "#C586C0",
            "variable": "#94dbfd",

            "struct": "#4eaab0",
            "typedef": "#4ec9b0",
            "macro": "#beb7ff",

            "number": "#6897BB",
            "string": "#cd9069",

            "field": "#DADADA",

        },
            "globals":
        {
            "foreground": "var(foreground)",
            "background": "var(background)",
        },

        "rules":
        [
            {
                "name": "variable",
                "scope": "semantic_var",
                "foreground": "var(variable)",
                "background": "var(background1)"
            },
            {
                "name": "param",
                "scope": "semantic_param",
                "foreground": "var(parameter)",
                "background": "var(background1)"
            },
            {
                "name": "struct",
                "scope": "semantic_struct, semantic_enum",
                "foreground": "var(struct)",
                "background": "var(background1)"
            },
            {
                "name": "type",
                "scope": "semantic_type",
                "foreground": "var(typedef)",
                "background": "var(background1)"
            },
            {
                "name": "macro",
                "scope": "semantic_macro",
                "foreground": "var(macro)",
                "background": "var(background1)"
            },

            {
                "name": "enumField",
                "scope": "semantic_enumfield",
                "foreground": "var(field)",
                "background": "var(background1)",
                "font_style": "italic"
            },

            {
                "name": "field",
                "scope": "semantic_field",
                "foreground": "var(field)",
                "background": "var(background1)",
            },

            {
                "name": "function",
                "scope": "semantic_func",
                "foreground": "var(function)",
                "background": "var(background1)"
            },
        ]
        '''

import sublime_plugin
import time

class SemanticListener(sublime_plugin.EventListener, sublime_plugin.TextChangeListener):  	
    def on_post_save_async(self, view):
        view.run_command('lsp_semantic')

    def on_activated_async(self, view): # this needs work, doesn't always highlight on the first try when activating a view
        view.run_command('lsp_semantic')

    def on_text_changed_async(self, changes):
     for change in changes:
        if len(change.str) == 1 and (change.str == ' ' or change.str == ';' or change.str == '.'):
            time.sleep(.5)
            self.buffer.views()[0].run_command('lsp_semantic')
