"""Automotive job marketplace.

Jobs hang off the existing company record (odex.road.mechanic.workshop), so a
workshop, a spare parts supplier or any other listing type can post vacancies
without duplicating company data anywhere.
"""

import logging
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

MANAGER_GROUP = 'odex_road_mechanic.group_road_mechanic_manager'
ALLOWED_CV_TYPES = ('pdf', 'doc', 'docx', 'odt', 'rtf')
MAX_CV_BYTES = 8 * 1024 * 1024


class JobCategory(models.Model):
    _name = 'odex.road.mechanic.job.category'
    _description = 'Road Mechanic Job Category'
    _inherit = ['odex.road.mechanic.slug.mixin']
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    icon = fields.Char(string='Icon Class', default='fa-wrench')
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
    job_ids = fields.One2many(
        'odex.road.mechanic.job', 'job_category_id', string='Jobs')
    job_count = fields.Integer(compute='_compute_job_count')

    _sql_constraints = [
        ('slug_uniq', 'unique(slug)', 'The URL slug must be unique.'),
    ]

    @api.depends('job_ids')
    def _compute_job_count(self):
        data = self.env['odex.road.mechanic.job'].sudo()._read_group(
            [('job_category_id', 'in', self.ids), ('state', '=', 'published')],
            ['job_category_id'], ['__count'])
        mapped = {category.id: count for category, count in data}
        for record in self:
            record.job_count = mapped.get(record.id, 0)


class JobSkill(models.Model):
    _name = 'odex.road.mechanic.job.skill'
    _description = 'Road Mechanic Job Skill'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'This skill already exists.'),
    ]


class Job(models.Model):
    _name = 'odex.road.mechanic.job'
    _description = 'Road Mechanic Job Posting'
    _inherit = ['odex.road.mechanic.slug.mixin', 'mail.thread',
                'mail.activity.mixin', 'website.seo.metadata']
    _order = ('is_featured desc, priority desc, published_date desc, '
              'create_date desc, id desc')

    name = fields.Char(string='Job Title', required=True, tracking=True, index=True)
    workshop_id = fields.Many2one(
        'odex.road.mechanic.workshop', string='Company', required=True,
        ondelete='cascade', index=True, tracking=True)
    partner_id = fields.Many2one(
        related='workshop_id.partner_id', store=True, string='Company Contact')
    company_logo = fields.Image(related='workshop_id.logo', string='Company Logo')
    is_company_verified = fields.Boolean(
        related='workshop_id.is_verified', store=True, string='Verified Company')
    job_category_id = fields.Many2one(
        'odex.road.mechanic.job.category', string='Job Category', required=True,
        ondelete='restrict', index=True)
    job_type = fields.Selection([
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('temporary', 'Temporary'),
        ('internship', 'Internship'),
    ], required=True, default='full_time', index=True, tracking=True)
    job_type_label = fields.Char(compute='_compute_labels')

    experience_min = fields.Integer(string='Minimum Experience (years)', default=0)
    experience_max = fields.Integer(string='Maximum Experience (years)', default=0)
    experience_label = fields.Char(compute='_compute_experience_label', store=True)
    experience_band = fields.Selection([
        ('entry', 'Entry Level (0-2 years)'),
        ('mid', 'Mid Level (2-5 years)'),
        ('senior', 'Senior Level (5+ years)'),
    ], compute='_compute_experience_label', store=True, index=True)

    use_company_location = fields.Boolean(string='Use Company Location', default=True)
    location_id = fields.Many2one(
        'odex.road.mechanic.location', string='Area', ondelete='set null', index=True)
    emirate = fields.Selection(
        selection=lambda self: self.env['odex.road.mechanic.workshop']._fields[
            'emirate'].selection, index=True)
    city = fields.Char()
    area = fields.Char()
    location_label = fields.Char(compute='_compute_location_label', store=True)

    salary_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('annual', 'Annual'),
        ('hourly', 'Hourly'),
        ('negotiable', 'Negotiable'),
        ('undisclosed', 'Not Disclosed'),
    ], default='undisclosed', required=True)
    salary_min = fields.Monetary(currency_field='currency_id')
    salary_max = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id.id)
    salary_label = fields.Char(compute='_compute_salary_label')

    description = fields.Html(string='Job Description', sanitize=True, required=True)
    requirements = fields.Html(string='Requirements', sanitize=True)
    short_description = fields.Char(
        compute='_compute_short_description', store=True,
        help='Plain text summary used on the job cards.')
    skill_ids = fields.Many2many(
        'odex.road.mechanic.job.skill', 'odex_rm_job_skill_rel', 'job_id', 'skill_id',
        string='Skills')

    application_method = fields.Selection([
        ('platform', 'Through Road Mechanic'),
        ('url', 'External application link'),
    ], default='platform', required=True,
        help='Applications always reach the application email; an external link '
             'sends the applicant to your own careers page instead.')
    application_email = fields.Char(string='Application Email', required=True)
    application_url = fields.Char(string='Application URL')
    contact_person = fields.Char()
    contact_phone = fields.Char()
    show_contact = fields.Boolean(
        string='Show Contact Publicly', default=False,
        help='Contact person and phone stay private unless this is ticked.')
    application_deadline = fields.Date(index=True)
    allow_reapplication = fields.Boolean(string='Allow Re-application', default=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('published', 'Published'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ], default='draft', required=True, index=True, tracking=True)
    state_label = fields.Char(compute='_compute_labels')
    published_date = fields.Datetime(readonly=True, copy=False)
    closed_date = fields.Datetime(readonly=True, copy=False)
    rejection_reason = fields.Text(readonly=True, copy=False)
    rejected_date = fields.Datetime(readonly=True, copy=False)
    rejected_by = fields.Many2one('res.users', readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approved_date = fields.Datetime(readonly=True, copy=False)

    is_featured = fields.Boolean(string='Featured', index=True, tracking=True)
    priority = fields.Integer(default=0, index=True)
    website_published = fields.Boolean(
        compute='_compute_website_published', store=True, index=True)
    is_open = fields.Boolean(compute='_compute_is_open')
    active = fields.Boolean(default=True)

    application_ids = fields.One2many(
        'odex.road.mechanic.job.application', 'job_id', string='Applications')
    application_count = fields.Integer(compute='_compute_application_count')
    new_application_count = fields.Integer(compute='_compute_application_count')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('job_type', 'state')
    def _compute_labels(self):
        types = dict(self._fields['job_type'].selection)
        states = dict(self._fields['state'].selection)
        for record in self:
            record.job_type_label = types.get(record.job_type, '')
            record.state_label = states.get(record.state, '')

    @api.depends('experience_min', 'experience_max')
    def _compute_experience_label(self):
        for record in self:
            low, high = record.experience_min or 0, record.experience_max or 0
            if high and high > low:
                record.experience_label = _('%(low)s - %(high)s Years Experience',
                                            low=low, high=high)
            elif low:
                record.experience_label = _('%s+ Years Experience', low)
            else:
                record.experience_label = _('Entry level - no experience required')
            reference = high or low
            if reference <= 2 and low < 2:
                record.experience_band = 'entry'
            elif low >= 5:
                record.experience_band = 'senior'
            else:
                record.experience_band = 'mid'

    @api.depends('use_company_location', 'location_id', 'emirate', 'city', 'area',
                 'workshop_id.location_id', 'workshop_id.city', 'workshop_id.emirate')
    def _compute_location_label(self):
        emirates = dict(self.env['odex.road.mechanic.workshop']._fields[
            'emirate'].selection)
        for record in self:
            if record.use_company_location and record.workshop_id:
                source = record.workshop_id
                parts = [source.area or source.city,
                         emirates.get(source.emirate, '')]
            else:
                parts = [record.area or record.city or record.location_id.name,
                         emirates.get(record.emirate, '')]
            record.location_label = ', '.join([p for p in parts if p]) or _('UAE')

    @api.depends('salary_type', 'salary_min', 'salary_max')
    def _compute_salary_label(self):
        labels = dict(self._fields['salary_type'].selection)
        for record in self:
            if record.salary_type in ('undisclosed', False):
                record.salary_label = ''
            elif record.salary_type == 'negotiable':
                record.salary_label = _('Negotiable')
            elif record.salary_min or record.salary_max:
                symbol = record.currency_id.symbol or record.currency_id.name or ''
                if record.salary_max and record.salary_max > record.salary_min:
                    amount = '%s%s - %s%s' % (symbol, int(record.salary_min),
                                              symbol, int(record.salary_max))
                else:
                    amount = '%s%s' % (symbol, int(record.salary_min or record.salary_max))
                record.salary_label = '%s (%s)' % (amount, labels[record.salary_type])
            else:
                record.salary_label = ''

    @api.depends('description')
    def _compute_short_description(self):
        for record in self:
            text = self._html_to_text(record.description or '')
            record.short_description = (text[:220] + '...') if len(text) > 220 else text

    @api.depends('state')
    def _compute_website_published(self):
        for record in self:
            record.website_published = record.state == 'published'

    @api.depends('state', 'application_deadline')
    def _compute_is_open(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_open = (
                record.state == 'published'
                and (not record.application_deadline
                     or record.application_deadline >= today))

    def _compute_application_count(self):
        data = self.env['odex.road.mechanic.job.application'].sudo()._read_group(
            [('job_id', 'in', self.ids)], ['job_id', 'state'], ['__count'])
        totals, fresh = {}, {}
        for job, state, count in data:
            totals[job.id] = totals.get(job.id, 0) + count
            if state == 'applied':
                fresh[job.id] = fresh.get(job.id, 0) + count
        for record in self:
            record.application_count = totals.get(record.id, 0)
            record.new_application_count = fresh.get(record.id, 0)

    @staticmethod
    def _html_to_text(value):
        import re
        text = re.sub(r'<[^>]+>', ' ', value or '')
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        return re.sub(r'\s+', ' ', text).strip()

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('experience_min', 'experience_max')
    def _check_experience(self):
        for record in self:
            if record.experience_min < 0 or record.experience_max < 0:
                raise ValidationError(_('Experience cannot be negative.'))
            if record.experience_max and record.experience_max < record.experience_min:
                raise ValidationError(
                    _('Maximum experience must be greater than the minimum.'))

    @api.constrains('salary_min', 'salary_max', 'salary_type')
    def _check_salary(self):
        for record in self:
            if record.salary_min < 0 or record.salary_max < 0:
                raise ValidationError(_('Salary cannot be negative.'))
            if record.salary_max and record.salary_max < record.salary_min:
                raise ValidationError(
                    _('Maximum salary must be greater than the minimum.'))

    @api.constrains('application_deadline')
    def _check_deadline(self):
        for record in self:
            if record.application_deadline and record.state == 'draft' \
                    and record.application_deadline < fields.Date.context_today(record):
                raise ValidationError(_('The application deadline is in the past.'))

    @api.constrains('application_email')
    def _check_application_email(self):
        import re
        pattern = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')
        for record in self:
            if record.application_email and not pattern.match(record.application_email):
                raise ValidationError(_('Please enter a valid application email.'))

    @api.constrains('application_method', 'application_url')
    def _check_application_url(self):
        for record in self:
            if record.application_method == 'url' and not record.application_url:
                raise ValidationError(
                    _('An external application link is required for this method.'))

    @api.onchange('workshop_id', 'use_company_location')
    def _onchange_company_defaults(self):
        if self.workshop_id and not self.application_email:
            self.application_email = self.workshop_id.email

    # ------------------------------------------------------------------
    # Protected fields: a company cannot promote or approve its own job
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        protected = {'is_featured', 'priority', 'state', 'approved_by',
                     'approved_date', 'published_date'}
        is_manager = self.env.su or self.env.user.has_group(MANAGER_GROUP)
        Workshop = self.env['odex.road.mechanic.workshop']
        for vals in vals_list:
            if not is_manager:
                for field in list(protected.intersection(vals)):
                    if field == 'state' and vals[field] in ('draft', 'pending'):
                        continue
                    del vals[field]
            # the slug carries the company and the area, as the brief asks:
            # /jobs/auto-technician-speedfix-dubai
            if not vals.get('slug'):
                workshop = Workshop.browse(vals.get('workshop_id')).exists()
                vals['slug'] = ' '.join(filter(None, [
                    vals.get('name'), workshop.name,
                    workshop.area or workshop.city]))
        return super().create(vals_list)

    def write(self, vals):
        protected = {'is_featured', 'priority', 'approved_by', 'approved_date',
                     'rejection_reason', 'rejected_by'}
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            blocked = protected.intersection(vals)
            if blocked:
                raise AccessError(
                    _('Only the Road Mechanic team can change: %s.',
                      ', '.join(sorted(blocked))))
            if vals.get('state') in ('published', 'rejected'):
                raise AccessError(
                    _('A job is published or rejected by the Road Mechanic team.'))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_submit(self):
        for record in self:
            if record.state not in ('draft', 'rejected'):
                raise UserError(_('Only a draft or rejected job can be submitted.'))
            record.state = 'pending'
            record._notify('odex_road_mechanic.mail_template_job_submitted')
        return True

    def action_approve(self):
        self._check_manager()
        for record in self:
            if record.state not in ('pending', 'closed', 'expired', 'rejected'):
                raise UserError(_('This job cannot be published from its current state.'))
            record.write({
                'state': 'published',
                'published_date': record.published_date or fields.Datetime.now(),
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
                'rejection_reason': False,
            })
            record._notify('odex_road_mechanic.mail_template_job_approved')
        return True

    def action_reject(self, reason=None):
        self._check_manager()
        for record in self:
            record.write({
                'state': 'rejected',
                'rejection_reason': reason or record.rejection_reason
                                    or _('No reason provided.'),
                'rejected_by': self.env.user.id,
                'rejected_date': fields.Datetime.now(),
            })
            record._notify('odex_road_mechanic.mail_template_job_rejected')
        return True

    def action_close(self):
        for record in self:
            record.write({'state': 'closed', 'closed_date': fields.Datetime.now()})
        return True

    def action_reset_draft(self):
        for record in self:
            record.state = 'draft'
        return True

    def _check_manager(self):
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_('Only the Road Mechanic team can do this.'))

    def _notify(self, template_xmlid):
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            return
        for record in self:
            try:
                template.sudo().send_mail(record.id, force_send=False)
            except Exception:  # noqa: BLE001 - a mail failure never blocks the flow
                _logger.exception('Road Mechanic: job mail %s failed', template_xmlid)

    @api.model
    def _cron_expire_jobs(self):
        """Close applications on jobs whose deadline has passed."""
        today = fields.Date.context_today(self)
        expired = self.sudo().search([
            ('state', '=', 'published'),
            ('application_deadline', '!=', False),
            ('application_deadline', '<', today),
        ])
        if expired:
            expired.write({'state': 'expired', 'closed_date': fields.Datetime.now()})
        return True

    # ------------------------------------------------------------------
    # Website helpers
    # ------------------------------------------------------------------
    @api.model
    def _public_domain(self):
        return [('state', '=', 'published')]

    def logo_url(self, size='180x180'):
        self.ensure_one()
        if self.workshop_id.logo:
            return '/web/image/odex.road.mechanic.workshop/%s/logo/%s' % (
                self.workshop_id.id, size)
        return '/odex_road_mechanic/static/src/img/logo_placeholder.png'

    def job_url(self):
        self.ensure_one()
        return '/jobs/%s' % self.slug

    def action_view_applications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Applications - %s', self.name),
            'res_model': 'odex.road.mechanic.job.application',
            'view_mode': 'list,form',
            'domain': [('job_id', '=', self.id)],
            'context': {'default_job_id': self.id},
        }

    def can_apply(self):
        self.ensure_one()
        return self.is_open and self.application_method == 'platform'


class JobApplication(models.Model):
    _name = 'odex.road.mechanic.job.application'
    _description = 'Road Mechanic Job Application'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Reference', default=lambda self: _('New'), copy=False, readonly=True)
    job_id = fields.Many2one(
        'odex.road.mechanic.job', string='Job', required=True, ondelete='cascade',
        index=True)
    workshop_id = fields.Many2one(
        related='job_id.workshop_id', store=True, string='Company', index=True)
    applicant_user_id = fields.Many2one('res.users', string='User', index=True)
    applicant_partner_id = fields.Many2one('res.partner', string='Contact', index=True)

    applicant_name = fields.Char(string='Full Name', required=True)
    email = fields.Char(required=True)
    phone = fields.Char(required=True)
    experience_years = fields.Float(string='Years of Experience')
    current_location = fields.Char()
    linkedin_url = fields.Char(string='LinkedIn / Portfolio')
    cover_letter = fields.Text()
    resume = fields.Binary(string='Resume / CV', attachment=True)
    resume_filename = fields.Char()

    consent_given = fields.Boolean(string='Consent Given', readonly=True)
    consent_date = fields.Datetime(readonly=True)

    state = fields.Selection([
        ('applied', 'Applied'),
        ('review', 'Under Review'),
        ('shortlisted', 'Shortlisted'),
        ('interview', 'Interview'),
        ('selected', 'Selected'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ], default='applied', required=True, index=True, tracking=True)
    state_label = fields.Char(compute='_compute_state_label')
    notes = fields.Text(string='Internal Notes')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_application', 'unique(job_id, applicant_user_id)',
         'You have already applied for this job.'),
    ]

    @api.depends('state')
    def _compute_state_label(self):
        labels = dict(self._fields['state'].selection)
        for record in self:
            record.state_label = labels.get(record.state, '')

    @api.constrains('resume_filename')
    def _check_resume_type(self):
        for record in self:
            if not record.resume_filename:
                continue
            extension = record.resume_filename.rsplit('.', 1)[-1].lower()
            if extension not in ALLOWED_CV_TYPES:
                raise ValidationError(
                    _('A CV must be a PDF or a document file (%s).',
                      ', '.join(ALLOWED_CV_TYPES)))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'odex.road.mechanic.job.application') or _('New')
        records = super().create(vals_list)
        records._notify_new_application()
        return records

    def _notify_new_application(self):
        company = self.env.ref(
            'odex_road_mechanic.mail_template_job_application_company',
            raise_if_not_found=False)
        applicant = self.env.ref(
            'odex_road_mechanic.mail_template_job_application_applicant',
            raise_if_not_found=False)
        for record in self:
            for template in (company, applicant):
                if not template:
                    continue
                try:
                    template.sudo().send_mail(record.id, force_send=False)
                except Exception:  # noqa: BLE001
                    _logger.exception(
                        'Road Mechanic: application mail failed for %s', record.id)

    def write(self, vals):
        result = super().write(vals)
        if 'state' in vals:
            template = self.env.ref(
                'odex_road_mechanic.mail_template_job_application_status',
                raise_if_not_found=False)
            if template:
                for record in self:
                    try:
                        template.sudo().send_mail(record.id, force_send=False)
                    except Exception:  # noqa: BLE001
                        _logger.exception('Road Mechanic: status mail failed')
        return result

    def action_set_state(self, state):
        if state not in dict(self._fields['state'].selection):
            raise UserError(_('Unknown application status.'))
        return self.write({'state': state})


class JobReject(models.TransientModel):
    """Rejecting a job always records a reason the company can act on."""

    _name = 'odex.road.mechanic.job.reject'
    _description = 'Reject Job Posting'

    job_ids = fields.Many2many(
        'odex.road.mechanic.job', 'odex_rm_job_reject_rel', 'reject_id', 'job_id',
        string='Jobs', required=True,
        default=lambda self: self.env.context.get('active_ids', []))
    reason = fields.Text(string='Rejection Reason', required=True)

    def action_reject(self):
        self.ensure_one()
        self.job_ids.action_reject(self.reason)
        return {'type': 'ir.actions.act_window_close'}
