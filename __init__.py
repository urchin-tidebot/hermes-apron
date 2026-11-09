"""Hermes plugin discovery entry point; implementation is an installable package."""


def register(ctx):
    from hermes_apron import register as register_plugin

    register_plugin(ctx)
