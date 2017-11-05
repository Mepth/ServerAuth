#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This code was originally taken from https://github.com/zeuxisoo/python-pluginplot
import logging



class PluginException(Exception):
    pass


class Plugin(object):
    def __init__(self, name="Plugin", description="", version=""):
        self.deferred_events = []
        self.name = name
        self.description = description
        self.version = version
        self.version_prefix = "" if version == "" else "v"
        self.logger = logging.getLogger(
            "{name} {prefix}{version}".format(name=name, prefix=self.version_prefix, version=version))
        self.logger.setLevel(logging.INFO)
        self.log = self.logger.info
        self.log("Initialized successfully...")

    # Event wrapper
    def event(self, event_name=None):
        def wrapper(method):
            self.add_deferred_method(event_name, method)
            return method

        return wrapper

    def add_deferred_method(self, event_name, method):
        if event_name is None:
            event_name = method.__name__
        self.deferred_events.append(lambda target: target.add_event(event_name, method))

    # Register event
    def register(self, plugin):
        for deferred_event in self.deferred_events:
            deferred_event(plugin)
