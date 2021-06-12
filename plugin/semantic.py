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


VARIABLE   = 1
PARAMETER  = 2
FUNCTION   = 3
FIELD      = 6
STRUCT     = 8
ENUM       = 9
ENUM_FIELD = 10
TYPEDEF    = 17
MACRO      = 18
# 5 4 7 9  

class LspSemanticCommand(LspTextCommand):

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
        # TODO: For code actions it makes more sense to use the whole selection under mouse (if available)
        # rather than just the hover point.

        def run_async() -> None:
            listener = wm.listener_for_view(self.view)
            if not listener:
                return
            if not only_diagnostics:
                self.request_symbol_semantic_async(listener, hover_point)
            self._diagnostics_by_config, covering = listener.diagnostics_touching_point_async(hover_point)
            # if self._diagnostics_by_config:
            #     self.show_hover(listener, hover_point, only_diagnostics)
            # if not only_diagnostics:
            #     actions_manager.request_for_region_async(
            #         self.view, covering, self._diagnostics_by_config,
            #         functools.partial(self.handle_code_actions, listener, hover_point))

        sublime.set_timeout_async(run_async)

    def request_symbol_semantic_async(self, listener: AbstractViewListener, point: int) -> None:
        session = listener.session('hoverProvider', point)
        if session:
            params = {"textDocument": text_document_identifier(self.view)}
            session.send_request_async(
                Request("textDocument/semanticTokens/full", params, self.view),
                lambda response: self.handle_response(listener, response, point))

    def handle_response(self, listener: AbstractViewListener, response: Optional[Any], point: int) -> None:
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

            if things[3] == MACRO:
                my_macros.append(my_region)
            if things[3] == STRUCT:
                my_structs.append(my_region)
            if things[3] == FIELD:
                my_fields.append(my_region)
            if things[3] == ENUM:
                my_enums.append(my_region)
            if things[3] == ENUM_FIELD:
                my_enum_fields.append(my_region)

            if things[3] == FUNCTION:
                my_funcs.append(my_region)

            if things[3] == TYPEDEF or things[3] == 11:
                my_types.append(my_region)
            if things[3] == PARAMETER:
                my_params.append(my_region)
            if things[3] == VARIABLE:
                my_vars.append(my_region)

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
