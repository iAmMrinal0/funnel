# -*- coding: utf-8 -*-

import unicodecsv
from cStringIO import StringIO
from flask import g, flash, redirect, render_template, Response, request, jsonify
from baseframe import _
from coaster.views import load_model, jsonp, requestargs

from .. import app, lastuser
from ..models import db, ProposalSpace, ProposalSpaceSection, Proposal
from ..forms import ProposalSpaceForm
from .proposal import proposal_headers, proposal_data, proposal_data_flat
from .schedule import schedule_data


@app.route('/new', methods=['GET', 'POST'])
@lastuser.requires_permission('siteadmin')
def space_new():
    form = ProposalSpaceForm(model=ProposalSpace)
    form.timezone.data = app.config.get('TIMEZONE')
    if form.validate_on_submit():
        space = ProposalSpace(user=g.user)
        form.populate_obj(space)
        db.session.add(space)
        db.session.commit()
        flash(_("Your new space has been created"), 'info')
        return redirect(space.url_for(), code=303)
    return render_template('baseframe/autoform.html', form=form, title=_("Create a new proposal space"), submit=_("Create space"))


@app.route('/<space>/')
@load_model(ProposalSpace, {'name': 'space'}, 'space',
    permission='view', addlperms=lastuser.permissions)
def space_view(space):
    sections = ProposalSpaceSection.query.filter_by(proposal_space=space, public=True).order_by('title').all()
    confirmed = Proposal.query.filter_by(proposal_space=space, confirmed=True).order_by(db.desc('created_at')).all()
    unconfirmed = Proposal.query.filter_by(proposal_space=space, confirmed=False).order_by(db.desc('created_at')).all()
    return render_template('space.html', space=space, description=space.description, sections=sections,
        confirmed=confirmed, unconfirmed=unconfirmed, is_siteadmin=lastuser.has_permission('siteadmin'))


@app.route('/<space>/json')
@load_model(ProposalSpace, {'name': 'space'}, 'space',
    permission='view', addlperms=lastuser.permissions)
def space_view_json(space):
    sections = ProposalSpaceSection.query.filter_by(proposal_space=space, public=True).order_by('title').all()
    proposals = Proposal.query.filter_by(proposal_space=space).order_by(db.desc('created_at')).all()
    return jsonp(**{
        'space': {
            'name': space.name,
            'title': space.title,
            'datelocation': space.datelocation,
            'timezone': space.timezone,
            'start': space.date.isoformat() if space.date else None,
            'end': space.date_upto.isoformat() if space.date_upto else None,
            'status': space.status,
            },
        'sections': [{'name': s.name, 'title': s.title, 'description': s.description} for s in sections],
        'venues': [{
            'name': venue.name,
            'title': venue.title,
            'description': venue.description.html,
            'address1': venue.address1,
            'address2': venue.address2,
            'city': venue.city,
            'state': venue.state,
            'postcode': venue.postcode,
            'country': venue.country,
            'latitude': venue.latitude,
            'longitude': venue.longitude
            } for venue in space.venues],
        'rooms': [{
            'name': room.scoped_name,
            'title': room.title,
            'description': room.description.html,
            'venue': room.venue.name,
            'bgcolor': room.bgcolor,
            } for room in space.rooms],
        'proposals': [proposal_data(proposal) for proposal in proposals],
        'schedule': schedule_data(space),
        })


@app.route('/<space>/csv')
@load_model(ProposalSpace, {'name': 'space'}, 'space',
    permission='view', addlperms=lastuser.permissions)
def space_view_csv(space):
    if lastuser.has_permission('siteadmin'):
        usergroups = [g.name for g in space.usergroups]
    else:
        usergroups = []
    proposals = Proposal.query.filter_by(proposal_space=space).order_by(db.desc('created_at')).all()
    outfile = StringIO()
    out = unicodecsv.writer(outfile, encoding='utf-8')
    out.writerow(proposal_headers + ['votes_' + group for group in usergroups])
    for proposal in proposals:
        out.writerow(proposal_data_flat(proposal, usergroups))
    outfile.seek(0)
    return Response(unicode(outfile.getvalue(), 'utf-8'), mimetype='text/plain')


@app.route('/<space>/edit', methods=['GET', 'POST'])
@load_model(ProposalSpace, {'name': 'space'}, 'space',
    permission=('edit-space', 'siteadmin'), addlperms=lastuser.permissions)
def space_edit(space):
    form = ProposalSpaceForm(obj=space, model=ProposalSpace)
    if request.method == 'GET' and not space.timezone:
        form.timezone.data = app.config.get('TIMEZONE')
    if form.validate_on_submit():
        form.populate_obj(space)
        db.session.commit()
        flash(_("Your changes have been saved"), 'info')
        return redirect(space.url_for(), code=303)
    return render_template('baseframe/autoform.html', form=form, title=_("Edit proposal space"), submit=_("Save changes"))


@app.route('/<space>/update_venue_colors', methods=['POST'])
@load_model(ProposalSpace, {'name': 'space'}, 'space',
    permission=('siteadmin'), addlperms=lastuser.permissions)
@requestargs('id[]', 'color[]')
def update_venue_colors(space, id, color):
    colors = dict([(id[i], col.replace('#', '')) for i, col in enumerate(color)])
    for room in space.rooms:
        if room.scoped_name in colors:
            room.bgcolor = colors[room.scoped_name]
    db.session.commit()
    return jsonify(status=True)
