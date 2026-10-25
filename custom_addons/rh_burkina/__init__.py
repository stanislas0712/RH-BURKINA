from . import models


def _post_init_hook(env):
    """Crée les séquences RH pour toutes les sociétés existantes."""
    env['res.company'].search([])._rh_create_sequences()
