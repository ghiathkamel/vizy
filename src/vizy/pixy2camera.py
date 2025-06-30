#
# This file is part of Vizy
#
# All Vizy source code is provided under the terms of the
# GNU General Public License v2 (http://www.gnu.org/licenses/gpl-2.0.html).
# Those wishing to use Vizy source code, software and/or
# technologies under different licensing terms should contact us at
# support@charmedlabs.com.
#
"""Pixy2 camera integration.

This module provides a lightweight wrapper around the `pixy2` Python
package from https://github.com/charmedlabs/pixy2.  The external package
must be installed separately before this module can be used.  Only a
small subset of the Pixy2 functionality is exposed here.
"""

import logging

try:
    import pixy2
except ImportError:  # pragma: no cover - pixy2 is optional
    pixy2 = None
    logging.warning("pixy2 package not installed; Pixy2Camera unavailable")


class Pixy2Camera:
    """Minimal Pixy2 camera wrapper."""

    def __init__(self):
        if pixy2 is None:
            raise ImportError("pixy2 package not installed")
        self._pixy = pixy2.Pixy2()
        self._pixy.init()

    def get_blocks(self, signature=0, max_blocks=10):
        """Return detected color blocks.

        Parameters
        ----------
        signature : int, optional
            Signature to filter on. Default is 0 which returns all
            signatures.
        max_blocks : int, optional
            Maximum number of blocks to return.
        """
        return self._pixy.get_blocks(signature=signature, count=max_blocks)

    def close(self):
        """Close the connection to the camera."""
        self._pixy.close()
