from odoo import models, fields, api


class ResGroups(models.Model):
    """Extension res.groups — compteur d'utilisateurs pour la vue liste des rôles."""
    _inherit = 'res.groups'

    nb_utilisateurs = fields.Integer(
        string='Utilisateurs',
        compute='_compute_nb_utilisateurs',
    )

    @api.depends('users')
    def _compute_nb_utilisateurs(self):
        for groupe in self:
            groupe.nb_utilisateurs = len(groupe.users)


class ResUsers(models.Model):
    """Extension res.users — rôle RH principal pour le regroupement en vue liste."""
    _inherit = 'res.users'

    role_rh_id = fields.Many2one(
        'res.groups',
        string='Rôle RH',
        compute='_compute_role_rh',
        store=True,
        index=True,
        help="Rôle hiérarchique RH principal de l'utilisateur (du plus élevé au plus bas).",
    )

    @api.depends('groups_id')
    def _compute_role_rh(self):
        # Ordre décroissant : le premier groupe trouvé est le rôle principal affiché
        HIERARCHIE = [
            'rh_burkina.group_rh_admin',
            'rh_burkina.group_rh_manager',
            'rh_burkina.group_rh_user',
            'rh_burkina.group_rh_employe',
        ]
        # Résolution des XML IDs hors de la boucle pour éviter des requêtes répétées
        groupes = {
            xml_id: self.env.ref(xml_id, raise_if_not_found=False)
            for xml_id in HIERARCHIE
        }
        for user in self:
            user.role_rh_id = False
            for xml_id in HIERARCHIE:
                groupe = groupes.get(xml_id)
                if groupe and groupe in user.groups_id:
                    user.role_rh_id = groupe
                    break
