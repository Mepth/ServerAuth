#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This code was originally taken from https://github.com/zeuxisoo/python-pluginplot
import builtins
import imp
import os
import sys
import threading
import traceback
import types

local_data = threading.local()

shared_space = types.ModuleType(__name__ + '.shared_space')
shared_space.__path__ = []
sys.modules[shared_space.__name__] = shared_space


class PluginException(Exception): pass


class EventError(PluginException): pass


class PluginSystem(object):
    def __init__(self, folder=None):
        self.events = {}
        self.folder = folder

    def add_event(self, name, method):
        if name in self.events:
            self.events[name].append(method)
        else:
            self.events[name] = [method]

    def call_event(self, name, *args, **kwargs):
        events_ = self.events.get(name)
        if not events_:
            pass
            # raise EventError("Not found event named: {0}".format(name))
        else:
            for event_ in events_:
                try:
                    event_(*args, **kwargs)
                except:
                    print(traceback.print_exc())
            return None

    def register_event(self, event):
        event.register(self)

    def register_events(self):
        if not self.folder:
            raise PluginException("Plugin.folder can not be None")
        else:
            self._init_plugin_files()

    def _init_plugin_files(self):
        for folder_path, folder_names, filenames in os.walk(self.folder):
            for filename in filenames:
                if filename.endswith('.py') and filename != "__init__.py":
                    # path/to/plugins/plugin/foo.py > plugin/foo.py > plugin.foo > shared_space.plugin.foo
                    full_plugin_path = os.path.join(folder_path, filename)
                    base_plugin_path = os.path.relpath(full_plugin_path, self.folder)
                    base_plugin_name = os.path.splitext(base_plugin_path)[0].replace(os.path.sep, '.')
                    module_source_name = "{0}.file_{1}".format(shared_space.__name__, base_plugin_name)
                    loaded_module = imp.load_module(
                        module_source_name,
                        *imp.find_module(os.path.splitext(filename)[0], [folder_path])
                    )
                    # TODO: Add support for any instance name of Plugin() class
                    self.register_event(loaded_module.plugin)

    def __enter__(self):
        local_data.plugin_stacks = [self]
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            local_data.plugin_stacks.pop()
        except:
            pass


def override_import(import_method):
    def wrapper(name, globals=None, locals=None, fromlist=None, level=0):
        # Try to get current plugin object
        try:
            plugin_object = local_data.plugin_stacks[-1]
        except (AttributeError, IndexError):
            plugin_object = None
        return import_method(name, globals, locals, fromlist, level)

    return wrapper


builtins.__import__ = override_import(builtins.__import__)

