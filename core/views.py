from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta, datetime

from .models import (
    Season,
    GameType,
    Participation,
    GameRules,
    Round,
    SinglesChallenge,
    TeamChallenge,
    SinglesFrame,
    SinglesRoll,
    TeamFrame,
    TeamRoll,
)
from .forms import (
    ProfileCompletionForm,
    SeasonForm,
    GameTypeForm,
    ParticipationForm,
    GameRulesForm,
    RoundCreateForm,
    PromoteWinnersForm,
)


def home(request):
    return render(request, 'core/home.html')


@login_required
def complete_profile(request):
    """
    After signup, redirect users here to fill in names, gender, phone.
    If the profile is already complete, bounce to the dashboard.
    """
    user = request.user
    if user.first_name and user.primary_phone:
        return redirect('dashboard')

    if request.method == 'POST':
        form = ProfileCompletionForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile completed successfully!')
            return redirect('dashboard')
    else:
        form = ProfileCompletionForm(instance=user)

    return render(request, 'core/complete_profile.html', {'form': form})


@login_required
def dashboard(request):
    """
    Main user dashboard after login/profile completion.
    """
    user = request.user
    if not user.first_name or not user.primary_phone:
        return redirect('complete_profile')

    return render(request, 'core/dashboard.html')

from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def admin_dashboard(request):
    """
    Dashboard for staff to manage objects.
    """
    seasons = Season.objects.all().order_by('-start_date')
    selected_season = None
    
    season_id = request.GET.get('season')
    if season_id:
        selected_season = seasons.filter(id=season_id).first()
    
    if not selected_season and seasons.exists():
        selected_season = seasons.filter(is_active=True).first() or seasons.first()
        
    game_types = GameType.objects.all()
    participations = []
    
    if selected_season:
        participations = Participation.objects.filter(season=selected_season).select_related('game_type')
        
    return render(request, 'core/admin_dashboard.html', {
        'seasons': seasons,
        'selected_season': selected_season,
        'game_types': game_types,
        'participations': participations,
    })


# ——— Season CRUD ———

@login_required
def season_list(request):
    seasons = Season.objects.all().order_by('-start_date')
    return render(request, 'core/season_list.html', {'seasons': seasons})

@staff_member_required
def season_detail(request, pk):
    from django.db.models import Sum
    season = get_object_or_404(Season, pk=pk)
    
    participants_count = season.participants.count()
    teams_count = season.teams.count()
    rounds = season.rounds.all().order_by('start_date')
    
    singles_fixtures_count = 0
    team_fixtures_count = 0
    for r in rounds:
        singles_fixtures_count += r.singles_challenges.count()
        team_fixtures_count += r.team_challenges.count()
        
    total_fixtures = singles_fixtures_count + team_fixtures_count
    
    # Calculate simple revenue:
    # Look at participations for this season and estimate based on counts
    revenue = 0
    for p in season.participations.all():
        if p.name == 'Single':
            revenue += p.charge * participants_count
        elif p.name in ['Double', 'Trio', 'Four']:
            revenue += p.charge * teams_count

    return render(request, 'core/season_detail.html', {
        'season': season,
        'participants_count': participants_count,
        'teams_count': teams_count,
        'rounds': rounds,
        'total_fixtures': total_fixtures,
        'revenue': revenue,
    })

@login_required
def season_create(request):
    if request.method == 'POST':
        form = SeasonForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Season created successfully!')
            return redirect('season_list')
    else:
        form = SeasonForm()
    return render(request, 'core/manage_form.html', {
        'form': form,
        'title': 'Create Season',
        'back_url': 'season_list',
    })


@login_required
def season_edit(request, pk):
    season = get_object_or_404(Season, pk=pk)
    if request.method == 'POST':
        form = SeasonForm(request.POST, instance=season)
        if form.is_valid():
            form.save()
            messages.success(request, 'Season updated successfully!')
            return redirect('season_list')
    else:
        form = SeasonForm(instance=season)
    return render(request, 'core/manage_form.html', {
        'form': form,
        'title': f'Edit Season — {season.name}',
        'back_url': 'season_list',
    })


@login_required
def season_delete(request, pk):
    season = get_object_or_404(Season, pk=pk)
    if request.method == 'POST':
        season.delete()
        messages.success(request, 'Season deleted.')
        return redirect('season_list')
    return render(request, 'core/confirm_delete.html', {
        'object': season,
        'back_url': 'season_list',
    })


# ——— GameType CRUD ———

@login_required
def gametype_list(request):
    game_types = GameType.objects.all().order_by('name')
    return render(request, 'core/gametype_list.html', {'game_types': game_types})


@login_required
def gametype_create(request):
    if request.method == 'POST':
        form = GameTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Game type created successfully!')
            return redirect('gametype_list')
    else:
        form = GameTypeForm()
    return render(request, 'core/manage_form.html', {
        'form': form,
        'title': 'Create Game Type',
        'back_url': 'gametype_list',
    })


@login_required
def gametype_edit(request, pk):
    gt = get_object_or_404(GameType, pk=pk)
    if request.method == 'POST':
        form = GameTypeForm(request.POST, instance=gt)
        if form.is_valid():
            form.save()
            messages.success(request, 'Game type updated successfully!')
            return redirect('gametype_list')
    else:
        form = GameTypeForm(instance=gt)
    return render(request, 'core/manage_form.html', {
        'form': form,
        'title': f'Edit Game Type — {gt.name}',
        'back_url': 'gametype_list',
    })


@login_required
def gametype_delete(request, pk):
    gt = get_object_or_404(GameType, pk=pk)
    if request.method == 'POST':
        gt.delete()
        messages.success(request, 'Game type deleted.')
        return redirect('gametype_list')
    return render(request, 'core/confirm_delete.html', {
        'object': gt,
        'back_url': 'gametype_list',
    })


# ——— Participation CRUD ———

@login_required
def participation_list(request):
    participations = Participation.objects.select_related('season', 'game_type').all().order_by('-season__start_date', 'name')
    return render(request, 'core/participation_list.html', {'participations': participations})


@login_required
def participation_create(request):
    if request.method == 'POST':
        form = ParticipationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Participation created successfully!')
            return redirect('participation_list')
    else:
        form = ParticipationForm()
    return render(request, 'core/manage_form.html', {
        'form': form,
        'title': 'Create Participation',
        'back_url': 'participation_list',
    })


@login_required
def participation_edit(request, pk):
    p = get_object_or_404(Participation, pk=pk)
    if request.method == 'POST':
        form = ParticipationForm(request.POST, instance=p)
        if form.is_valid():
            form.save()
            messages.success(request, 'Participation updated successfully!')
            return redirect('participation_list')
    else:
        form = ParticipationForm(instance=p)
    enrolled_users_count = p.enrolled_users.count()
    enrolled_teams_count = p.enrolled_teams.count()
    
    is_single = (p.name == 'Single')
    if is_single:
        revenue = enrolled_users_count * p.charge
    else:
        revenue = enrolled_teams_count * p.charge

    rounds = (
        p.rounds.all()
        .order_by('start_date', 'id')
        .annotate(
            singles_match_count=Count('singles_challenges', distinct=True),
            team_match_count=Count('team_challenges', distinct=True),
        )
    )

    ctx = {
        'form': form,
        'participation': p,
        'title': f'Manage Participation — {p.name} ({p.season.name})',
        'enrolled_users_count': enrolled_users_count,
        'enrolled_teams_count': enrolled_teams_count,
        'revenue': revenue,
        'is_single': is_single,
        'rounds': rounds,
    }
    if request.user.is_staff:
        ctx['round_create_form'] = RoundCreateForm()
        ctx['promote_form'] = PromoteWinnersForm(p)
    return render(request, 'core/participation_edit.html', ctx)


@login_required
def participation_round_panel(request, pk, round_id):
    """HTML fragment for one round (lazy-loaded on the participation edit tabs)."""
    p = get_object_or_404(Participation, pk=pk)
    is_single = p.name == 'Single'
    if is_single:
        r = get_object_or_404(
            Round.objects.filter(game_type=p).prefetch_related(
                'singles_challenges__player_1',
                'singles_challenges__player_2',
            ),
            pk=round_id,
        )
    else:
        r = get_object_or_404(
            Round.objects.filter(game_type=p).prefetch_related(
                'team_challenges__team_1',
                'team_challenges__team_2',
            ),
            pk=round_id,
        )
    return render(request, 'core/participation_edit_round_panel.html', {
        'participation': p,
        'r': r,
        'is_single': is_single,
    })


@staff_member_required
@require_POST
def participation_challenge_schedule(request, pk, challenge_id, challenge_type):
    """Update scheduled start/end for a singles or team challenge (staff only)."""
    p = get_object_or_404(Participation, pk=pk)
    start_raw = request.POST.get('start_datetime', '').strip()
    end_raw = request.POST.get('end_datetime', '').strip()
    if not start_raw or not end_raw:
        return JsonResponse({'ok': False, 'error': 'Start and end times are required.'}, status=400)
    try:
        start_dt = datetime.fromisoformat(start_raw)
        end_dt = datetime.fromisoformat(end_raw)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Invalid date or time.'}, status=400)
    if timezone.is_naive(start_dt):
        start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
    if timezone.is_naive(end_dt):
        end_dt = timezone.make_aware(end_dt, timezone.get_current_timezone())
    if end_dt < start_dt:
        return JsonResponse({'ok': False, 'error': 'End time must be after start time.'}, status=400)

    if challenge_type == 'singles':
        ch = get_object_or_404(SinglesChallenge, pk=challenge_id, round__game_type=p)
    elif challenge_type == 'team':
        ch = get_object_or_404(TeamChallenge, pk=challenge_id, round__game_type=p)
    else:
        return JsonResponse({'ok': False, 'error': 'Invalid challenge type.'}, status=400)
    ch.start_datetime = start_dt
    ch.end_datetime = end_dt
    ch.save(update_fields=['start_datetime', 'end_datetime'])
    return JsonResponse({'ok': True})


def _get_or_create_roll(roll_model, frame, order):
    r = roll_model.objects.filter(frame=frame, order=order).first()
    if r:
        return r
    return roll_model.objects.create(frame=frame, order=order, score=0)


def _ensure_singles_match_frames(challenge):
    r = challenge.round
    for user in (challenge.player_1, challenge.player_2):
        for order in range(1, 11):
            frame, _ = SinglesFrame.objects.get_or_create(
                round=r,
                participant=user,
                order=order,
                defaults={'played': False},
            )
            for roll_order in (1, 2):
                _get_or_create_roll(SinglesRoll, frame, roll_order)


def _ensure_team_match_frames(challenge):
    r = challenge.round
    for team in (challenge.team_1, challenge.team_2):
        for order in range(1, 11):
            frame, _ = TeamFrame.objects.get_or_create(
                round=r,
                team=team,
                order=order,
                defaults={'participant': team.captain, 'played': False},
            )
            for roll_order in (1, 2):
                _get_or_create_roll(TeamRoll, frame, roll_order)


def _parse_roll_field(raw):
    if raw is None or str(raw).strip() == '':
        return 0
    try:
        v = int(raw)
    except ValueError:
        return 0
    return max(0, min(10, v))


@staff_member_required
def match_score_singles(request, pk, challenge_id):
    """Create 10 frames per bowler and edit roll scores (singles)."""
    p = get_object_or_404(Participation, pk=pk)
    if p.name != 'Single':
        messages.error(request, 'This participation is not singles.')
        return redirect('participation_edit', pk=pk)
    challenge = get_object_or_404(SinglesChallenge, pk=challenge_id, round__game_type=p)

    if request.method == 'POST':
        _ensure_singles_match_frames(challenge)
        with transaction.atomic():
            for side, user in (('p1', challenge.player_1), ('p2', challenge.player_2)):
                for fn in range(1, 11):
                    frame = SinglesFrame.objects.get(round=challenge.round, participant=user, order=fn)
                    for rn in (1, 2):
                        key = f'{side}_f{fn}_r{rn}'
                        roll = _get_or_create_roll(SinglesRoll, frame, rn)
                        roll.score = _parse_roll_field(request.POST.get(key))
                        roll.save()
                    frame.played = frame.rolls.exclude(score=0).exists()
                    frame.save(update_fields=['played'])
        messages.success(request, 'Scores saved.')
        return redirect('match_score_singles', pk=pk, challenge_id=challenge_id)

    _ensure_singles_match_frames(challenge)
    p1_rows, p2_rows = [], []
    for user, rows in ((challenge.player_1, p1_rows), (challenge.player_2, p2_rows)):
        for order in range(1, 11):
            frame = SinglesFrame.objects.get(round=challenge.round, participant=user, order=order)
            rolls_map = {roll.order: roll.score for roll in frame.rolls.all()}
            rows.append({
                'order': order,
                'r1': rolls_map.get(1, 0),
                'r2': rolls_map.get(2, 0),
            })
    score_rows = []
    for i in range(10):
        score_rows.append({
            'order': i + 1,
            'p1_r1': p1_rows[i]['r1'],
            'p1_r2': p1_rows[i]['r2'],
            'p2_r1': p2_rows[i]['r1'],
            'p2_r2': p2_rows[i]['r2'],
        })

    return render(request, 'core/match_score_singles.html', {
        'participation': p,
        'challenge': challenge,
        'score_rows': score_rows,
        'p1_label': (challenge.player_1.get_full_name() or '').strip() or challenge.player_1.email,
        'p2_label': (challenge.player_2.get_full_name() or '').strip() or challenge.player_2.email,
    })


@staff_member_required
def match_score_team(request, pk, challenge_id):
    """Create 10 frames per team and edit roll scores (team category)."""
    p = get_object_or_404(Participation, pk=pk)
    if p.name == 'Single':
        messages.error(request, 'Use singles scoring for individual matches.')
        return redirect('participation_edit', pk=pk)
    challenge = get_object_or_404(TeamChallenge, pk=challenge_id, round__game_type=p)

    if request.method == 'POST':
        _ensure_team_match_frames(challenge)
        with transaction.atomic():
            for side, team in (('t1', challenge.team_1), ('t2', challenge.team_2)):
                for fn in range(1, 11):
                    frame = TeamFrame.objects.get(round=challenge.round, team=team, order=fn)
                    for rn in (1, 2):
                        key = f'{side}_f{fn}_r{rn}'
                        roll = _get_or_create_roll(TeamRoll, frame, rn)
                        roll.score = _parse_roll_field(request.POST.get(key))
                        roll.save()
                    frame.played = frame.rolls.exclude(score=0).exists()
                    frame.save(update_fields=['played'])
        messages.success(request, 'Scores saved.')
        return redirect('match_score_team', pk=pk, challenge_id=challenge_id)

    _ensure_team_match_frames(challenge)
    t1_rows, t2_rows = [], []
    for team, rows in ((challenge.team_1, t1_rows), (challenge.team_2, t2_rows)):
        for order in range(1, 11):
            frame = TeamFrame.objects.get(round=challenge.round, team=team, order=order)
            rolls_map = {roll.order: roll.score for roll in frame.rolls.all()}
            rows.append({
                'order': order,
                'r1': rolls_map.get(1, 0),
                'r2': rolls_map.get(2, 0),
            })
    score_rows = []
    for i in range(10):
        score_rows.append({
            'order': i + 1,
            't1_r1': t1_rows[i]['r1'],
            't1_r2': t1_rows[i]['r2'],
            't2_r1': t2_rows[i]['r1'],
            't2_r2': t2_rows[i]['r2'],
        })

    return render(request, 'core/match_score_team.html', {
        'participation': p,
        'challenge': challenge,
        'score_rows': score_rows,
        't1_label': challenge.team_1.name,
        't2_label': challenge.team_2.name,
    })


def _next_empty_round_after(participation, from_round, is_single):
    ordered = list(participation.rounds.order_by('start_date', 'id'))
    try:
        idx = ordered.index(from_round)
    except ValueError:
        return None
    for r in ordered[idx + 1:]:
        n = r.singles_challenges.count() if is_single else r.team_challenges.count()
        if n == 0:
            return r
    return None


@staff_member_required
def participation_round_create(request, pk):
    p = get_object_or_404(Participation, pk=pk)
    if request.method != 'POST':
        return redirect('participation_edit', pk=pk)
    form = RoundCreateForm(request.POST)
    if not form.is_valid():
        for field_errors in form.errors.values():
            for err in field_errors:
                messages.error(request, err)
        if form.non_field_errors():
            for err in form.non_field_errors():
                messages.error(request, err)
        return redirect('participation_edit', pk=pk)
    data = form.cleaned_data
    r = Round.objects.create(
        name=data['name'],
        season=p.season,
        game_type=p,
        start_date=data['start_date'],
        end_date=data['end_date'],
    )
    if p.name == 'Single':
        r.participants.set(p.enrolled_users.all())
    else:
        r.teams.set(p.enrolled_teams.all())
    messages.success(request, f'Round "{r.name}" created for this category.')
    return redirect('participation_edit', pk=pk)


@staff_member_required
def participation_promote_winners(request, pk):
    p = get_object_or_404(Participation, pk=pk)
    if request.method != 'POST':
        return redirect('participation_edit', pk=pk)
    is_single = p.name == 'Single'
    form = PromoteWinnersForm(p, request.POST)
    if not form.is_valid():
        for field_errors in form.errors.values():
            for err in field_errors:
                messages.error(request, err)
        return redirect('participation_edit', pk=pk)
    from_round = form.cleaned_data['from_round']
    if from_round.game_type_id != p.id:
        messages.error(request, 'Invalid round for this participation.')
        return redirect('participation_edit', pk=pk)

    to_round = _next_empty_round_after(p, from_round, is_single)
    if not to_round:
        messages.error(
            request,
            'No empty round exists after the one you selected. Create a new round with a later start date first, then run promote again.',
        )
        return redirect('participation_edit', pk=pk)

    now = timezone.now()
    end = now + timedelta(hours=2)
    ties = unplayed = 0
    winners = []

    if is_single:
        qs = from_round.singles_challenges.all()
        if not qs.exists():
            messages.error(request, 'That round has no matches yet.')
            return redirect('participation_edit', pk=pk)
        for c in qs:
            w = c.get_winner_player()
            if w:
                winners.append(w)
            elif c.get_p1_score == 0 and c.get_p2_score == 0:
                unplayed += 1
            else:
                ties += 1
    else:
        qs = from_round.team_challenges.all()
        if not qs.exists():
            messages.error(request, 'That round has no matches yet.')
            return redirect('participation_edit', pk=pk)
        for c in qs:
            w = c.get_winner_team()
            if w:
                winners.append(w)
            elif c.get_t1_score == 0 and c.get_t2_score == 0:
                unplayed += 1
            else:
                ties += 1

    if len(winners) < 2:
        messages.error(
            request,
            'Need at least two decisive winners to pair into the next round. Enter scores or break ties first.',
        )
        return redirect('participation_edit', pk=pk)

    created = 0
    bye_note = None
    with transaction.atomic():
        if is_single:
            for i in range(0, len(winners) - 1, 2):
                SinglesChallenge.objects.create(
                    round=to_round,
                    player_1=winners[i],
                    player_2=winners[i + 1],
                    start_datetime=now,
                    end_datetime=end,
                )
                created += 1
            if len(winners) % 2 == 1:
                u = winners[-1]
                bye_note = (u.get_full_name() or '').strip() or u.email
        else:
            for i in range(0, len(winners) - 1, 2):
                TeamChallenge.objects.create(
                    round=to_round,
                    team_1=winners[i],
                    team_2=winners[i + 1],
                    start_datetime=now,
                    end_datetime=end,
                )
                created += 1
            if len(winners) % 2 == 1:
                bye_note = winners[-1].name

    parts = [f'Created {created} match(es) in "{to_round.name}".']
    if ties:
        parts.append(f'Skipped {ties} tied match(es) (no winner).')
    if unplayed:
        parts.append(f'Skipped {unplayed} unplayed match(es).')
    if bye_note:
        parts.append(f'Odd number of winners: bye for {bye_note} (no match created for this entry).')
    messages.success(request, ' '.join(parts))
    return redirect('participation_edit', pk=pk)


@login_required
def participation_delete(request, pk):
    p = get_object_or_404(Participation, pk=pk)
    if request.method == 'POST':
        p.delete()
        messages.success(request, 'Participation deleted.')
        return redirect('participation_list')
    return render(request, 'core/confirm_delete.html', {
        'object': p,
        'back_url': 'participation_list',
    })


# ——— GameRules CRUD ———

@login_required
def gamerules_list(request):
    rules = GameRules.objects.select_related('game_type').all().order_by('game_type__name', 'order')
    return render(request, 'core/gamerules_list.html', {'rules': rules})


@login_required
def gamerules_create(request):
    if request.method == 'POST':
        form = GameRulesForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Rule created successfully!')
            return redirect('gamerules_list')
    else:
        form = GameRulesForm()
    return render(request, 'core/manage_form.html', {
        'form': form,
        'title': 'Create Game Rule',
        'back_url': 'gamerules_list',
    })


@login_required
def gamerules_edit(request, pk):
    rule = get_object_or_404(GameRules, pk=pk)
    if request.method == 'POST':
        form = GameRulesForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, 'Rule updated successfully!')
            return redirect('gamerules_list')
    else:
        form = GameRulesForm(instance=rule)
    return render(request, 'core/manage_form.html', {
        'form': form,
        'title': f'Edit Rule #{rule.order}',
        'back_url': 'gamerules_list',
    })


@login_required
def gamerules_delete(request, pk):
    rule = get_object_or_404(GameRules, pk=pk)
    if request.method == 'POST':
        rule.delete()
        messages.success(request, 'Rule deleted.')
        return redirect('gamerules_list')
    return render(request, 'core/confirm_delete.html', {
        'object': rule,
        'back_url': 'gamerules_list',
    })
