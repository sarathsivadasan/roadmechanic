import base64
import logging
import re

from werkzeug.exceptions import NotFound

from odoo import fields, http, _
from odoo.http import request
from odoo.exceptions import AccessError
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')
ALLOWED_CV = ('pdf', 'doc', 'docx', 'odt', 'rtf')
MAX_CV_BYTES = 8 * 1024 * 1024


class JobWebsite(http.Controller):
    """Public job marketplace: listing, detail page and the application form."""

    def _common(self):
        env = request.env
        return {
            'job_categories': env['odex.road.mechanic.job.category'].search([]),
            'job_types': env['odex.road.mechanic.job']._fields['job_type'].selection,
            'job_bands': env['odex.road.mechanic.job']._fields[
                'experience_band'].selection,
            'job_emirates': env['odex.road.mechanic.workshop']._fields[
                'emirate'].selection,
        }

    def _published_job(self, slug):
        job = request.env['odex.road.mechanic.job'].search(
            [('slug', '=', slug)], limit=1)
        if not job or job.state not in ('published', 'closed', 'expired'):
            raise NotFound()
        return job

    # ------------------------------------------------------------------
    # /jobs
    # ------------------------------------------------------------------
    @http.route(['/jobs', '/jobs/page/<int:page>'], type='http', auth='public',
                website=True, sitemap=True)
    def jobs_index(self, page=1, **post):
        Job = request.env['odex.road.mechanic.job']
        domain = Job._public_domain()

        search = (post.get('search') or '').strip()[:80]
        if search:
            domain += ['|', '|', '|',
                       ('name', 'ilike', search),
                       ('workshop_id.name', 'ilike', search),
                       ('skill_ids.name', 'ilike', search),
                       ('job_category_id.name', 'ilike', search)]
        if post.get('category_id') and str(post['category_id']).isdigit():
            domain.append(('job_category_id', '=', int(post['category_id'])))
        if post.get('job_type') in dict(Job._fields['job_type'].selection):
            domain.append(('job_type', '=', post['job_type']))
        if post.get('band') in dict(Job._fields['experience_band'].selection):
            domain.append(('experience_band', '=', post['band']))
        emirate = post.get('emirate')
        if emirate in dict(request.env['odex.road.mechanic.workshop']._fields[
                'emirate'].selection):
            domain += ['|',
                       '&', ('use_company_location', '=', True),
                       ('workshop_id.emirate', '=', emirate),
                       '&', ('use_company_location', '=', False),
                       ('emirate', '=', emirate)]

        orders = {
            'latest': 'published_date desc, create_date desc, id desc',
            'oldest': 'published_date asc, create_date asc, id asc',
            'deadline': 'application_deadline asc, id desc',
            'relevant': None,
        }
        sort = post.get('sort') if post.get('sort') in orders else 'relevant'
        order = orders[sort]

        step = 10
        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            page = 1
        total = Job.search_count(domain)
        jobs = Job.search(domain, limit=step, offset=(page - 1) * step, order=order)

        url_args = {k: post[k] for k in
                    ('search', 'category_id', 'job_type', 'band', 'emirate', 'sort')
                    if post.get(k)}
        values = self._common()
        values.update({
            'jobs': jobs,
            'total': total,
            'featured_jobs': Job.search(
                Job._public_domain() + [('is_featured', '=', True)], limit=4),
            'pager': request.website.pager(
                url='/jobs', total=total, page=page, step=step, scope=5,
                url_args=url_args),
            'search': search,
            'filters': post,
            'sort': sort,
            'website': request.website,
        })
        return request.render('odex_road_mechanic.jobs_page', values)

    # ------------------------------------------------------------------
    # /jobs/<slug>
    # ------------------------------------------------------------------
    @http.route(['/jobs/<string:job_slug>'], type='http', auth='public',
                website=True, sitemap=False)
    def job_detail(self, job_slug, **post):
        job = self._published_job(job_slug)
        values = self._common()
        applied = False
        if request.env.user and not request.env.user._is_public():
            applied = bool(request.env['odex.road.mechanic.job.application'].sudo(
            ).search_count([('job_id', '=', job.id),
                            ('applicant_user_id', '=', request.env.user.id)]))
        values.update({
            'job': job,
            'main_object': job,
            'already_applied': applied,
            'related_jobs': request.env['odex.road.mechanic.job'].search(
                [('state', '=', 'published'),
                 ('job_category_id', '=', job.job_category_id.id),
                 ('id', '!=', job.id)], limit=3),
            'sent': post.get('sent'),
            'error': post.get('error'),
            'website': request.website,
        })
        return request.render('odex_road_mechanic.job_detail', values)

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    @http.route(['/jobs/<string:job_slug>/apply'], type='http', auth='public',
                methods=['POST'], website=True)
    def job_apply(self, job_slug, **post):
        job = self._published_job(job_slug)
        back = '/jobs/%s' % job.slug

        if post.get('orm_website_url'):  # honeypot
            return request.redirect('%s?sent=1#job-apply' % back)
        if not job.can_apply():
            return request.redirect('%s?error=closed#job-apply' % back)
        if post.get('consent') not in ('1', 'on', 'true'):
            return request.redirect('%s?error=consent#job-apply' % back)

        name = (post.get('applicant_name') or '').strip()
        email = (post.get('email') or '').strip()
        phone = (post.get('phone') or '').strip()
        if not name or not phone or not email or not EMAIL_RE.match(email):
            return request.redirect('%s?error=contact#job-apply' % back)

        user = request.env.user
        is_logged = user and not user._is_public()
        Application = request.env['odex.road.mechanic.job.application'].sudo()
        if is_logged and not job.allow_reapplication:
            if Application.search_count([('job_id', '=', job.id),
                                         ('applicant_user_id', '=', user.id)]):
                return request.redirect('%s?error=duplicate#job-apply' % back)
        elif not is_logged:
            if Application.search_count([('job_id', '=', job.id),
                                         ('email', '=ilike', email)]):
                return request.redirect('%s?error=duplicate#job-apply' % back)

        resume, filename = False, False
        upload = request.httprequest.files.get('resume')
        if upload and upload.filename:
            extension = upload.filename.rsplit('.', 1)[-1].lower()
            if extension not in ALLOWED_CV:
                return request.redirect('%s?error=filetype#job-apply' % back)
            content = upload.read(MAX_CV_BYTES + 1)
            if len(content) > MAX_CV_BYTES:
                return request.redirect('%s?error=filesize#job-apply' % back)
            resume = base64.b64encode(content)
            filename = upload.filename[:120]

        try:
            experience = float(post.get('experience_years') or 0)
        except (TypeError, ValueError):
            experience = 0.0

        try:
            Application.create({
                'job_id': job.id,
                'applicant_name': name[:120],
                'email': email[:120],
                'phone': phone[:40],
                'experience_years': max(0.0, experience),
                'current_location': (post.get('current_location') or '').strip()[:120]
                                    or False,
                'linkedin_url': (post.get('linkedin_url') or '').strip()[:250] or False,
                'cover_letter': (post.get('cover_letter') or '').strip()[:4000] or False,
                'resume': resume,
                'resume_filename': filename,
                'applicant_user_id': user.id if is_logged else False,
                'applicant_partner_id': user.partner_id.id if is_logged else False,
                'consent_given': True,
                'consent_date': fields.Datetime.now(),
            })
        except Exception:  # noqa: BLE001 - never leak a traceback publicly
            _logger.exception('Road Mechanic: job application failed')
            return request.redirect('%s?error=unknown#job-apply' % back)
        return request.redirect('%s?sent=1#job-apply' % back)


class JobPortal(CustomerPortal):
    """Company job management and the applicant's own applications."""

    def _owned_workshop(self, workshop_id):
        workshop = request.env['odex.road.mechanic.workshop'].browse(int(workshop_id))
        if not workshop.exists():
            raise NotFound()
        workshop.check_access('read')
        return workshop

    def _my_workshops(self):
        return request.env['odex.road.mechanic.workshop'].search(
            [('partner_id', '=', request.env.user.partner_id.id)])

    def _owned_job(self, job_id):
        job = request.env['odex.road.mechanic.job'].browse(int(job_id))
        if not job.exists():
            raise NotFound()
        try:
            job.check_access('write')
        except AccessError as error:
            raise NotFound() from error
        return job

    # ------------------------------------------------------------------
    # Garage Partner: job list and dashboard counters
    # ------------------------------------------------------------------
    @http.route(['/my/jobs'], type='http', auth='user', website=True)
    def portal_my_jobs(self, **post):
        Job = request.env['odex.road.mechanic.job']
        jobs = Job.search([])  # record rules restrict this to the user's own jobs
        values = self._prepare_portal_layout_values()
        values.update({
            'jobs': jobs,
            'workshops': self._my_workshops(),
            'counts': {
                'total': len(jobs),
                'published': len(jobs.filtered(lambda j: j.state == 'published')),
                'pending': len(jobs.filtered(lambda j: j.state == 'pending')),
                'closed': len(jobs.filtered(
                    lambda j: j.state in ('closed', 'expired'))),
                'applications': sum(jobs.mapped('application_count')),
            },
            'page_name': 'road_mechanic_jobs',
            'saved': post.get('saved'),
            'error': post.get('error'),
        })
        return request.render('odex_road_mechanic.portal_my_jobs', values)

    @http.route(['/my/job/new', '/my/job/<int:job_id>/edit'], type='http',
                auth='user', website=True)
    def portal_job_form(self, job_id=None, **post):
        job = self._owned_job(job_id) if job_id else request.env[
            'odex.road.mechanic.job']
        workshops = self._my_workshops()
        if not workshops:
            return request.redirect('/my/workshops')
        values = self._prepare_portal_layout_values()
        values.update({
            'job': job,
            'workshops': workshops,
            'job_categories': request.env['odex.road.mechanic.job.category'].search([]),
            'job_skills': request.env['odex.road.mechanic.job.skill'].search([]),
            'job_types': request.env['odex.road.mechanic.job']._fields[
                'job_type'].selection,
            'salary_types': request.env['odex.road.mechanic.job']._fields[
                'salary_type'].selection,
            'job_emirates': request.env['odex.road.mechanic.workshop']._fields[
                'emirate'].selection,
            'page_name': 'road_mechanic_jobs',
            'error': post.get('error'),
        })
        return request.render('odex_road_mechanic.portal_job_form', values)

    @http.route(['/my/job/save'], type='http', auth='user', methods=['POST'],
                website=True)
    def portal_job_save(self, **post):
        Job = request.env['odex.road.mechanic.job']
        job_id = post.get('job_id')
        job = self._owned_job(job_id) if job_id and job_id.isdigit() else False

        workshop_id = post.get('workshop_id')
        workshops = self._my_workshops()
        if not workshop_id or int(workshop_id) not in workshops.ids:
            return request.redirect('/my/jobs?error=company')

        def _int(value, default=0):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        def _float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        skills = [int(s) for s in request.httprequest.form.getlist('skill_ids')
                  if str(s).isdigit()]
        values = {
            'name': (post.get('name') or '').strip()[:120],
            'workshop_id': int(workshop_id),
            'job_category_id': _int(post.get('job_category_id')) or False,
            'job_type': post.get('job_type') or 'full_time',
            'experience_min': _int(post.get('experience_min')),
            'experience_max': _int(post.get('experience_max')),
            'use_company_location': post.get('use_company_location') in ('1', 'on'),
            'emirate': post.get('emirate') or False,
            'city': (post.get('city') or '').strip()[:80] or False,
            'area': (post.get('area') or '').strip()[:80] or False,
            'salary_type': post.get('salary_type') or 'undisclosed',
            'salary_min': _float(post.get('salary_min')),
            'salary_max': _float(post.get('salary_max')),
            'description': post.get('description') or '',
            'requirements': post.get('requirements') or '',
            'skill_ids': [(6, 0, skills)],
            'application_method': post.get('application_method') or 'platform',
            'application_email': (post.get('application_email') or '').strip()[:120],
            'application_url': (post.get('application_url') or '').strip()[:250] or False,
            'contact_person': (post.get('contact_person') or '').strip()[:120] or False,
            'contact_phone': (post.get('contact_phone') or '').strip()[:40] or False,
            'show_contact': post.get('show_contact') in ('1', 'on'),
            'application_deadline': post.get('application_deadline') or False,
        }
        if not values['name'] or not values['job_category_id'] \
                or not values['application_email']:
            return request.redirect('/my/jobs?error=missing')

        try:
            if job:
                job.write(values)
            else:
                job = Job.create(values)
            if post.get('submit_for_approval'):
                job.action_submit()
        except Exception:  # noqa: BLE001
            _logger.exception('Road Mechanic: job save failed')
            return request.redirect('/my/jobs?error=save')
        return request.redirect('/my/jobs?saved=1')

    @http.route(['/my/job/<int:job_id>/close'], type='http', auth='user',
                methods=['POST'], website=True)
    def portal_job_close(self, job_id, **post):
        self._owned_job(job_id).action_close()
        return request.redirect('/my/jobs?saved=1')

    @http.route(['/my/job/<int:job_id>/submit'], type='http', auth='user',
                methods=['POST'], website=True)
    def portal_job_submit(self, job_id, **post):
        self._owned_job(job_id).action_submit()
        return request.redirect('/my/jobs?saved=1')

    # ------------------------------------------------------------------
    # Garage Partner: applications to its own jobs
    # ------------------------------------------------------------------
    @http.route(['/my/job/<int:job_id>/applications'], type='http', auth='user',
                website=True)
    def portal_job_applications(self, job_id, **post):
        job = self._owned_job(job_id)
        values = self._prepare_portal_layout_values()
        values.update({
            'job': job,
            'applications': job.application_ids,
            'page_name': 'road_mechanic_jobs',
        })
        return request.render('odex_road_mechanic.portal_job_applications', values)

    @http.route(['/my/application/<int:application_id>/state'], type='http',
                auth='user', methods=['POST'], website=True)
    def portal_application_state(self, application_id, **post):
        application = request.env['odex.road.mechanic.job.application'].browse(
            application_id)
        if not application.exists():
            raise NotFound()
        try:
            application.check_access('write')
        except AccessError as error:
            raise NotFound() from error
        application.action_set_state(post.get('state') or 'review')
        return request.redirect('/my/job/%s/applications' % application.job_id.id)

    # ------------------------------------------------------------------
    # Customer: my applications
    # ------------------------------------------------------------------
    @http.route(['/my/applications'], type='http', auth='user', website=True)
    def portal_my_applications(self, **post):
        applications = request.env['odex.road.mechanic.job.application'].search(
            [('applicant_user_id', '=', request.env.user.id)])
        values = self._prepare_portal_layout_values()
        values.update({
            'applications': applications,
            'page_name': 'road_mechanic_applications',
        })
        return request.render('odex_road_mechanic.portal_my_applications', values)
