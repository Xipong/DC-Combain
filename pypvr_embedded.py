# -*- coding: utf-8 -*-
"""Embedded PyPVR wrapper.
Tries to import the real `pypvr` shipped with the app. If not found, provides a safe stub.
"""
try:
    import pypvr as pypvr  # prefer shipped module
except ImportError:
    import types, sys
    pypvr = types.ModuleType("pypvr")

    class _PypvrStub:
        """Fallback replacement for the real :class:`pypvr.Pypvr`.

        The original ``Decode`` implementation accepts several optional
        arguments.  In situations where the bundled ``pypvr`` module is not
        available we still want the application to run without raising a
        ``TypeError`` due to unexpected parameters.  Using ``*args`` and
        ``**kwargs`` ensures compatibility with any call signature while
        behaving as a no-op.
        """

        @staticmethod
        def Decode(*args, **kwargs):
            # Return 0 to keep GUI logic flowing (no-op)
            return 0

    pypvr.Pypvr = _PypvrStub
    # Make the stub importable as ``pypvr`` for code that expects the real
    # module to be present in ``sys.modules``.
    sys.modules.setdefault("pypvr", pypvr)
