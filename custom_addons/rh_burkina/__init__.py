from . import models
from . import wizards


def _post_init_hook(env):
    """Initialise les données RH sur une base existante."""
    env['res.company'].search([])._rh_create_sequences()
    # Matricule et ligne d'embauche pour les employés déjà présents
    employees = env['hr.employee'].with_context(active_test=False).search(
        [('matricule', '=', False)], order='id')
    for emp in employees:
        emp.matricule = env['ir.sequence'].with_company(
            emp.company_id).next_by_code('rh.employe')
    employees._rh_historiser_embauche()
