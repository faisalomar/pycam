# -*- coding: utf-8 -*-
"""
Copyright 2011 Lars Kruse <devel@sumpfralle.de>

This file is part of PyCAM.

PyCAM is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

PyCAM is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with PyCAM.  If not, see <http://www.gnu.org/licenses/>.
"""

import pycam.Plugins
from pycam.Flow.data_models import Tool
from pycam.Toolpath.Filters import toolpath_filter


class Tools(pycam.Plugins.ListPluginBase):

    DEPENDS = ["ParameterGroupManager"]
    CATEGORIES = ["Tool"]
    UI_FILE = "tools.ui"
    COLLECTION_ITEM_TYPE = pycam.Flow.data_models.Tool

    def setup(self):
        self.core.set("tools", self)
        if self.gui:
            tool_frame = self.gui.get_object("ToolBox")
            tool_frame.unparent()
            self.core.register_ui("main", "Tools", tool_frame, weight=10)
            self._gtk_handlers = []
            self._modelview = self.gui.get_object("ToolTable")
            self.set_gtk_modelview(self._modelview)
            self.register_model_update(lambda: self.core.emit_event("tool-list-changed"))
            for action, obj_name in ((self.ACTION_UP, "ToolMoveUp"),
                                     (self.ACTION_DOWN, "ToolMoveDown"),
                                     (self.ACTION_DELETE, "ToolDelete")):
                self.register_list_action_button(action, self.gui.get_object(obj_name))
            self._gtk_handlers.append((self.gui.get_object("ToolNew"), "clicked", self._tool_new))
            # parameters
            parameters_box = self.gui.get_object("ToolParameterBox")

            def clear_parameter_widgets():
                parameters_box.foreach(parameters_box.remove)

            def add_parameter_widget(item, name):
                # create a frame within an alignment and the item inside
                if item.get_parent():
                    item.unparent()
                frame_label = self._gtk.Label()
                frame_label.set_markup("<b>%s</b>" % name)
                frame = self._gtk.Frame()
                frame.set_label_widget(frame_label)
                align = self._gtk.Alignment()
                frame.add(align)
                align.set_padding(0, 3, 12, 3)
                align.add(item)
                frame.show_all()
                parameters_box.pack_start(frame, expand=True, fill=True, padding=0)

            self.core.register_ui_section("tool_parameters", add_parameter_widget,
                                          clear_parameter_widgets)
            self.core.get("register_parameter_group")(
                "tool", changed_set_event="tool-shape-changed",
                changed_set_list_event="tool-shape-list-changed",
                get_current_set_func=self._get_shape)
            self.size_widget = pycam.Gui.ControlsGTK.ParameterSection()
            self.core.register_ui("tool_parameters", "Size", self.size_widget.get_widget(),
                                  weight=10)
            self.core.register_ui_section("tool_size", self.size_widget.add_widget,
                                          self.size_widget.clear_widgets)
            self.speed_widget = pycam.Gui.ControlsGTK.ParameterSection()
            self.core.register_ui("tool_parameters", "Speed", self.speed_widget.get_widget(),
                                  weight=20)
            self.core.register_ui_section("tool_speed", self.speed_widget.add_widget,
                                          self.speed_widget.clear_widgets)
            # table updates
            cell = self.gui.get_object("ShapeCell")
            self.gui.get_object("ShapeColumn").set_cell_data_func(cell, self._render_tool_shape)
            self._gtk_handlers.append((self.gui.get_object("IDCell"), "edited",
                                       self._edit_tool_id))
            self._gtk_handlers.append((self.gui.get_object("NameCell"), "edited",
                                       self._edit_tool_name))
            self._treemodel = self.gui.get_object("ToolList")
            self._treemodel.clear()
            # selector
            self._gtk_handlers.append((self._modelview.get_selection(), "changed",
                                       "tool-selection-changed"))
            # shape selector
            self._gtk_handlers.append((self.gui.get_object("ToolShapeSelector"), "changed",
                                       "tool-shape-changed"))
            self._event_handlers = (
                ("tool-shape-list-changed", self._update_widgets),
                ("tool-selection-changed", self._tool_switch),
                ("tool-changed", self._store_tool_settings),
                ("tool-changed", self._trigger_table_update),
                ("tool-list-changed", self._trigger_table_update),
                ("tool-shape-changed", self._store_tool_settings))
            self.register_gtk_handlers(self._gtk_handlers)
            self.register_event_handlers(self._event_handlers)
            self._update_widgets()
            self._trigger_table_update()
            self._tool_switch()
        self.core.register_chain("toolpath_filters", self.get_toolpath_filters)
        self.core.register_namespace("tools", pycam.Plugins.get_filter(self))
        self.register_state_item("tools", self)
        return True

    def teardown(self):
        self.clear_state_items()
        self.core.unregister_namespace("tools")
        self.core.unregister_chain("toolpath_filters", self.get_toolpath_filters)
        if self.gui and self._gtk:
            self.core.unregister_ui("main", self.gui.get_object("ToolBox"))
            self.core.unregister_ui_section("tool_speed")
            self.core.unregister_ui_section("tool_size")
            self.core.unregister_ui("tool_parameters", self.size_widget.get_widget())
            self.core.unregister_ui("tool_parameters", self.speed_widget.get_widget())
            self.core.unregister_ui_section("tool_parameters")
            self.unregister_gtk_handlers(self._gtk_handlers)
            self.unregister_event_handlers(self._event_handlers)
        self.core.set("tools", None)
        self.clear()
        return True

    def _trigger_table_update(self):
        self.gui.get_object("IDColumn").set_cell_data_func(
            self.gui.get_object("IDCell"), self._render_tool_info, "tool_id")
        self.gui.get_object("NameColumn").set_cell_data_func(
            self.gui.get_object("NameCell"), self._render_tool_info, "name")
        self.gui.get_object("ShapeColumn").set_cell_data_func(
            self.gui.get_object("ShapeCell"), self._render_tool_shape)

    def _render_tool_info(self, column, cell, model, m_iter, key):
        tool = self.get_by_path(model.get_path(m_iter))
        if key in ("tool_id", ):
            text = tool.get_value(key)
        else:
            text = tool.get_application_value(key)
        cell.set_property("text", str(text))

    def _render_tool_shape(self, column, cell, model, m_iter, data):
        tool = self.get_by_path(model.get_path(m_iter))
        text = "%g%s" % (tool.diameter, self.core.get("unit"))
        cell.set_property("text", text)

    def _edit_tool_name(self, cell, path, new_text):
        tool = self.get_by_path(path)
        if tool and (new_text != tool.get_application_value("name")) and new_text:
            tool.set_application_value("name", new_text)
            self.core.emit_event("tool-list-changed")

    def _edit_tool_id(self, cell, path, new_text):
        tool = self.get_by_path(path)
        try:
            new_value = int(new_text)
        except ValueError:
            return
        if tool and (new_value != tool.get_value("tool_id")):
            tool.set_value("tool_id", new_value)

    def _get_shape(self, name=None):
        shapes = self.core.get("get_parameter_sets")("tool")
        if name is None:
            # find the currently selected one
            selector = self.gui.get_object("ToolShapeSelector")
            model = selector.get_model()
            index = selector.get_active()
            if index < 0:
                return None
            shape_name = model[index][1]
        else:
            shape_name = name
        if shape_name in shapes:
            return shapes[shape_name]
        else:
            return None

    def select_shape(self, name):
        selector = self.gui.get_object("ToolShapeSelector")
        for index, row in enumerate(selector.get_model()):
            if row[1] == name:
                selector.set_active(index)
                break
        else:
            selector.set_active(-1)

    def _update_widgets(self):
        selected = self._get_shape()
        model = self.gui.get_object("ToolShapeList")
        model.clear()
        shapes = list(self.core.get("get_parameter_sets")("tool").values())
        shapes.sort(key=lambda item: item["weight"])
        for shape in shapes:
            model.append((shape["label"], shape["name"]))
        # check if any on the tools became obsolete due to a missing plugin
        removal = []
        shape_names = [shape["name"] for shape in shapes]
        for index, tool in enumerate(self.get_all()):
            if not tool.get_value("shape").value in shape_names:
                removal.append(index)
        removal.reverse()
        for index in removal:
            self.pop(index)
        # show "new" only if a strategy is available
        self.gui.get_object("ToolNew").set_sensitive(len(model) > 0)
        selector_box = self.gui.get_object("ToolSelectorBox")
        if len(model) < 2:
            selector_box.hide()
        else:
            selector_box.show()
        if selected:
            self.select_shape(selected["name"])

    def _store_tool_settings(self):
        tool = self.get_selected()
        control_box = self.gui.get_object("ToolSettingsControlsBox")
        shape = self._get_shape()
        if tool is None or shape is None:
            control_box.hide()
        else:
            tool.set_value("shape", shape["name"])
            for key, value in self.core.get("get_parameter_values")("tool").items():
                tool.set_value(key, value)
            control_box.show()
            self._trigger_table_update()

    def _tool_switch(self, widget=None, data=None):
        tool = self.get_selected()
        control_box = self.gui.get_object("ToolSettingsControlsBox")
        if not tool:
            control_box.hide()
        else:
            self.core.block_event("tool-changed")
            self.core.block_event("tool-shape-changed")
            shape_name = tool.get_value("shape").value
            self.select_shape(shape_name)
            self.core.get("set_parameter_values")("tool", tool.get_dict())
            control_box.show()
            self.core.unblock_event("tool-shape-changed")
            self.core.unblock_event("tool-changed")
            # trigger a widget update
            self.core.emit_event("tool-shape-changed")

    def _tool_new(self, *args):
        existing_tool_ids = [tool.get_value("tool_id") for tool in self.get_all()]
        tool_id = 1
        while tool_id in existing_tool_ids:
            tool_id += 1
        tool_name = "Tool #{:d}".format(tool_id)
        new_tool = Tool(None,
                        {"shape": "flat_bottom", "radius": 1.0, "feed": 300, "tool_id": tool_id})
        new_tool.set_application_value("name", tool_name)
        self.select(new_tool)

    @toolpath_filter("tool", "tool_id")
    def get_toolpath_filters(self, tool_id):
        return [pycam.Toolpath.Filters.SelectTool(tool_id)]
