from .code_actions import CodeActionOrCommand
from .core.protocol import Diagnostic
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.sessions import SessionBufferProtocol
from .core.typing import List, Optional, Any, Dict, Tuple, Sequence
from .core.views import first_selection_region
from .core.windows import AbstractViewListener
from .core.views import text_document_identifier
import sublime


SUBLIME_WORD_MASK = 515

class LspSemanticCommand(LspTextCommand):

    capability = 'documentSymbolProvider'

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._base_dir = None   # type: Optional[str]

    def run(
        self,
        edit: sublime.Edit,
        only_diagnostics: bool = False,
        point: Optional[int] = None,
        event: Optional[dict] = None
    ) -> None:
        temp_point = point
        if temp_point is None:
            region = first_selection_region(self.view)
            if region is not None:
                temp_point = region.begin()
        if temp_point is None:
            return
        window = self.view.window()
        if not window:
            return
        hover_point = temp_point
        wm = windows.lookup(window)
        self._base_dir = wm.get_project_path(self.view.file_name() or "")
        self._hover = None  # type: Optional[Any]
        self._actions_by_config = {}  # type: Dict[str, List[CodeActionOrCommand]]
        self._diagnostics_by_config = []  # type: Sequence[Tuple[SessionBufferProtocol, Sequence[Diagnostic]]]

        def run_async() -> None:
            listener = wm.listener_for_view(self.view)
            if not listener:
                return
            if not only_diagnostics:
                self.request_symbol_semantic_async(listener, hover_point)
            self._diagnostics_by_config, covering = listener.diagnostics_touching_point_async(hover_point)

        sublime.set_timeout_async(run_async)

    def request_symbol_semantic_async(self, listener: AbstractViewListener, point: int) -> None:
        session = listener.session('hoverProvider', point)
        # session = self.best_session(self.capability)
        if session:
            token_types = None
            try:
                token_types = session.get_capability('semanticTokensProvider')['legend']['tokenTypes']
            except:
                return

            # print('LSP--tokenTypes-:   ', token_types)
            params = {"textDocument": text_document_identifier(self.view)}
            session.send_request_async(
                Request("textDocument/semanticTokens/full", params, self.view),
                lambda response: self.handle_response(listener, response, token_types))

    def handle_response(self, listener: AbstractViewListener, response: Optional[Any], token_types: list) -> None:
        # print("LSSSP:HOVER:RESPONSE:   ", response['data'])

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

        # self._hover = response

import sublime_plugin
class SemanticListener(sublime_plugin.EventListener):  	
    def on_post_save_async(self, view):
        view.run_command('lsp_semantic')

    def on_activated_async(self, view):
        view.run_command('lsp_semantic')

import time
class SemanticListenerTwo(sublime_plugin.TextChangeListener):
    def on_text_changed_async(self, changes):
		# [print('textChange: ',list(a.str))  for a in changes]
        for change in changes:
            if len(change.str) == 1 and (change.str == ' ' or change.str == ';' or change.str == '.'):
                time.sleep(.5)
                self.buffer.views()[0].run_command('lsp_semantic')
