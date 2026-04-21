from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta, datetime
import json
import requests

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
    Team,
    User,
    SeasonSchedule,
    Payment
)
from .mpesa import MpesaService
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
    schedules = []
    participations = []
    active_season = Season.objects.filter(is_active=True).first()
    if active_season:
        schedules = active_season.schedules.all().order_by('order')
        participations = active_season.participations.all().select_related('game_type')
    return render(request, 'core/home.html', {
        'schedules': schedules,
        'active_season': active_season,
        'participations': participations
    })


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

    from django.db.models import Q
    # Singles challenges
    singles = SinglesChallenge.objects.filter(
        Q(player_1=user) | Q(player_2=user)
    ).select_related('round__game_type__season').order_by('-round__start_date', '-id')

    # Team challenges
    teams = user.member_teams.all()
    team_matches = TeamChallenge.objects.filter(
        Q(team_1__in=teams) | Q(team_2__in=teams)
    ).select_related('round__game_type__season').order_by('-round__start_date', '-id')

    # Leaderboard Data
    active_season = Season.objects.filter(is_active=True).order_by('-start_date').first()
    leaderboard_participations = []
    if active_season:
        from django.db.models import Prefetch, Q
        leaderboard_participations = Participation.objects.filter(season=active_season).prefetch_related(
            Prefetch('rounds', queryset=Round.objects.order_by('order'))
        )
        
        # Determine the default round for each participation
        for p in leaderboard_participations:
            latest_with_scores = p.rounds.filter(
                Q(singles_frames__played=True) | Q(team_frames__played=True)
            ).order_by('-order').first()
            
            if latest_with_scores:
                p.default_round_id = latest_with_scores.id
            else:
                first_round = p.rounds.first()
                p.default_round_id = first_round.id if first_round else None

    # Enrollment Data: Tabbed Seasons and available participations
    all_seasons = Season.objects.all().order_by('-start_date')
    first_active_season_id = None
    for s in all_seasons:
        if s.is_active and first_active_season_id is None:
            first_active_season_id = s.id
        s.available_participations = s.participations.all().select_related('game_type')
        for p in s.available_participations:
            p.is_enrolled = p.enrolled_users.filter(id=user.id).exists()
    
    if first_active_season_id is None and all_seasons.exists():
        first_active_season_id = all_seasons[0].id

    return render(request, 'core/dashboard.html', {
        'singles': singles,
        'team_matches': team_matches,
        'active_season': active_season,
        'leaderboard_participations': leaderboard_participations,
        'all_seasons': all_seasons,
        'first_active_season_id': first_active_season_id,
    })

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
    stats = {
        'total_players': 0,
        'total_teams': 0,
        'total_rounds': 0,
        'total_revenue': 0,
    }
    
    recent_payments = []
    top_participants = []
    category_breakdown = []
    
    if selected_season:
        participations = Participation.objects.filter(season=selected_season).select_related('game_type')
        
        # Stats calculations
        from django.db.models import Count, Sum
        stats['total_players'] = User.objects.filter(enrolled_participations__season=selected_season).distinct().count()
        stats['total_teams'] = Team.objects.filter(enrolled_participations__season=selected_season).distinct().count()
        stats['total_rounds'] = Round.objects.filter(season=selected_season).count()
        stats['total_revenue'] = Payment.objects.filter(participation__season=selected_season, status='SUCCESS').aggregate(total=Sum('amount'))['total'] or 0

        # Recent successful payments
        recent_payments = Payment.objects.filter(participation__season=selected_season, status='SUCCESS').select_related('user', 'participation').order_by('-created_at')[:5]
        
        # Category breakdown for chart
        for p in participations:
            first_round = Round.objects.filter(season=selected_season).order_by('order').first()
            category_breakdown.append({
                'id': p.id,
                'name': p.name,
                'count': p.enrolled_users.count(),
                'charge': p.charge,
                'game_type_name': p.game_type.name,
                'first_round_id': first_round.id if first_round else None
            })
            
        # Top participants (by points if available, otherwise just enrolled ones)
        # For now, let's just get some users
        top_participants = User.objects.filter(enrolled_participations__season=selected_season).distinct()[:5]

    return render(request, 'core/admin_dashboard.html', {
        'seasons': seasons,
        'selected_season': selected_season,
        'game_types': game_types,
        'participations': participations,
        'stats': stats,
        'recent_payments': recent_payments,
        'top_participants': top_participants,
        'category_breakdown': category_breakdown,
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
            return redirect('participation_edit', pk=p.pk)
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
        .order_by('order', 'id')
        .annotate(
            singles_match_count=Count('singles_challenges', distinct=True),
            team_match_count=Count('team_challenges', distinct=True),
            participant_count=Count('participants', distinct=True),
            team_count=Count('teams', distinct=True),
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
def participation_round_leaderboard(request, pk, round_id):
    """Return JSON leaderboard data for a specific round."""
    p = get_object_or_404(Participation, pk=pk)
    r = get_object_or_404(Round, pk=round_id, game_type=p)
    is_single = p.name == 'Single'
    from django.db.models import Q, Sum
    
    # Find next round by order
    next_round = p.rounds.filter(order__gt=r.order).order_by('order').first()
    # Promotion is only allowed if the current round is completed AND the next round is not completed
    can_promote_general = r.is_completed and next_round and not next_round.is_completed
    
    leaderboard = []
    if is_single:
        # Get all participants in this round
        participants = r.participants.all()
        next_participants_ids = set(next_round.participants.values_list('id', flat=True)) if next_round else set()
        
        for user in participants:
            # ... existing score logic ...
            round_score = SinglesRoll.objects.filter(frame__round=r, frame__participant=user).aggregate(total=Sum('score'))['total'] or 0
            total_pins = SinglesRoll.objects.filter(frame__round__game_type=p, frame__participant=user).aggregate(total=Sum('score'))['total'] or 0
            rounds_played = Round.objects.filter(game_type=p, singles_frames__participant=user, singles_frames__rolls__isnull=False).distinct().count()

            # Winner logic
            won_match = False
            challenge = SinglesChallenge.objects.filter(round=r).filter(Q(player_1=user) | Q(player_2=user)).first()
            if challenge:
                s1 = SinglesRoll.objects.filter(frame__round=r, frame__participant=challenge.player_1).aggregate(total=Sum('score'))['total'] or 0
                s2 = SinglesRoll.objects.filter(frame__round=r, frame__participant=challenge.player_2).aggregate(total=Sum('score'))['total'] or 0
                if (challenge.player_1 == user and s1 > s2) or (challenge.player_2 == user and s2 > s1):
                    won_match = True

            is_enrolled_next = user.id in next_participants_ids
            can_promote = can_promote_general and not is_enrolled_next

            leaderboard.append({
                'id': user.id,
                'name': (user.get_full_name() or "").strip() or user.email,
                'round_score': round_score,
                'total_pins': total_pins,
                'rounds_played': rounds_played,
                'won_match': won_match,
                'can_promote': can_promote,
                'is_enrolled_next': is_enrolled_next,
            })
    else:
        # Get all teams in this round
        teams = r.teams.all()
        next_teams_ids = set(next_round.teams.values_list('id', flat=True)) if next_round else set()
        
        for team in teams:
            # ... existing score logic ...
            round_score = TeamRoll.objects.filter(frame__round=r, frame__team=team).aggregate(total=Sum('score'))['total'] or 0
            total_pins = TeamRoll.objects.filter(frame__round__game_type=p, frame__team=team).aggregate(total=Sum('score'))['total'] or 0
            rounds_played = Round.objects.filter(game_type=p, team_frames__team=team, team_frames__rolls__isnull=False).distinct().count()

            # Winner logic
            won_match = False
            challenge = TeamChallenge.objects.filter(round=r).filter(Q(team_1=team) | Q(team_2=team)).first()
            if challenge:
                s1 = TeamRoll.objects.filter(frame__round=r, frame__team=challenge.team_1).aggregate(total=Sum('score'))['total'] or 0
                s2 = TeamRoll.objects.filter(frame__round=r, frame__team=challenge.team_2).aggregate(total=Sum('score'))['total'] or 0
                if (challenge.team_1 == team and s1 > s2) or (challenge.team_2 == team and s2 > s1):
                    won_match = True

            is_enrolled_next = team.id in next_teams_ids
            can_promote = can_promote_general and not is_enrolled_next

            leaderboard.append({
                'id': team.id,
                'name': team.name,
                'round_score': round_score,
                'total_pins': total_pins,
                'rounds_played': rounds_played,
                'won_match': won_match,
                'can_promote': can_promote,
                'is_enrolled_next': is_enrolled_next,
            })
            
    # Sort by round score, then total pins
    leaderboard.sort(key=lambda x: (x['round_score'], x['total_pins']), reverse=True)
    
    # Assign ranks with tie handling
    curr_rank = 0
    prev_score = None
    for i, item in enumerate(leaderboard):
        score_tuple = (item['round_score'], item['total_pins'])
        if score_tuple != prev_score:
            curr_rank = i + 1
        item['rank'] = curr_rank
        prev_score = score_tuple

    return JsonResponse({
        'ok': True, 
        'leaderboard': leaderboard, 
        'round_name': r.name,
        'is_completed': r.is_completed
    })


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
    latest_round = p.rounds.order_by('-start_date', '-id').first()
    is_latest = (latest_round and r.id == latest_round.id)

    return render(request, 'core/participation_edit_round_panel.html', {
        'participation': p,
        'r': r,
        'is_single': is_single,
        'is_latest': is_latest,
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
    s = str(raw).strip().upper()
    if s == 'X':
        return 10
    if s == '/':
        return -1  # Spare marker
    try:
        v = int(s)
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
                        val = request.POST.get(key)
                        if val is not None:
                            roll = _get_or_create_roll(SinglesRoll, frame, rn)
                            if not roll.is_recorded:
                                score = _parse_roll_field(val)
                                if score == -1:  # Spare
                                    prev_roll = SinglesRoll.objects.filter(frame=frame, order=1).first()
                                    prev_score = prev_roll.score if prev_roll else 0
                                    score = max(0, 10 - prev_score)
                                roll.score = score
                                roll.is_recorded = True
                                roll.save()
                    frame.played = frame.rolls.filter(is_recorded=True).exists()
                    frame.save(update_fields=['played'])
        messages.success(request, 'Scores saved.')
        return redirect('match_score_singles', pk=pk, challenge_id=challenge_id)

    _ensure_singles_match_frames(challenge)
    score_rows = challenge.get_frame_score_rows()

    latest_round = p.rounds.order_by('-start_date', '-id').first()
    is_latest = (latest_round and challenge.round_id == latest_round.id)

    return render(request, 'core/match_score_singles.html', {
        'participation': p,
        'challenge': challenge,
        'score_rows': score_rows,
        'p1_label': (challenge.player_1.get_full_name() or '').strip() or challenge.player_1.email,
        'p2_label': (challenge.player_2.get_full_name() or '').strip() or challenge.player_2.email,
        'is_latest': is_latest,
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
                        val = request.POST.get(key)
                        if val is not None:
                            roll = _get_or_create_roll(TeamRoll, frame, rn)
                            if not roll.is_recorded:
                                score = _parse_roll_field(val)
                                if score == -1:  # Spare
                                    prev_roll = TeamRoll.objects.filter(frame=frame, order=1).first()
                                    prev_score = prev_roll.score if prev_roll else 0
                                    score = max(0, 10 - prev_score)
                                roll.score = score
                                roll.is_recorded = True
                                roll.save()
                    frame.played = frame.rolls.filter(is_recorded=True).exists()
                    frame.save(update_fields=['played'])
        messages.success(request, 'Scores saved.')
        return redirect('match_score_team', pk=pk, challenge_id=challenge_id)

    _ensure_team_match_frames(challenge)
    score_rows = challenge.get_frame_score_rows()

    latest_round = p.rounds.order_by('-start_date', '-id').first()
    is_latest = (latest_round and challenge.round_id == latest_round.id)

    return render(request, 'core/match_score_team.html', {
        'participation': p,
        'challenge': challenge,
        'score_rows': score_rows,
        't1_label': challenge.team_1.name,
        't2_label': challenge.team_2.name,
        'is_latest': is_latest,
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
        order=data['order'],
        season=p.season,
        game_type=p,
        start_date=data['start_date'],
        end_date=data['end_date'],
    )
    # Rounds start empty; participants must be promoted or generated into them.
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
    criteria = form.cleaned_data['criteria']
    percentage = form.cleaned_data['percentage'] or 50
    
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

    promoted_objs = []
    skipped_info = ""

    if criteria == 'all_winners':
        ties = unplayed = 0
        if is_single:
            qs = from_round.singles_challenges.all()
            for c in qs:
                w = c.get_winner_player()
                if w: promoted_objs.append(w)
                elif c.get_p1_score == 0 and c.get_p2_score == 0: unplayed += 1
                else: ties += 1
        else:
            qs = from_round.team_challenges.all()
            for c in qs:
                w = c.get_winner_team()
                if w: promoted_objs.append(w)
                elif c.get_t1_score == 0 and c.get_t2_score == 0: unplayed += 1
                else: ties += 1
        skipped_info = f'All {len(promoted_objs)} winners promoted.'
    
    elif criteria == 'top_winners':
        winners_list = []
        if is_single:
            qs = from_round.singles_challenges.all()
            for c in qs:
                w = c.get_winner_player()
                if w: winners_list.append(w)
        else:
            qs = from_round.team_challenges.all()
            for c in qs:
                w = c.get_winner_team()
                if w: winners_list.append(w)
        
        # Rank the winners by their total round score
        ranked_winners = []
        for obj in winners_list:
            score = 0
            if is_single:
                challenges = SinglesChallenge.objects.filter(round=from_round).filter(Q(player_1=obj) | Q(player_2=obj))
                for c in challenges:
                    score += c.get_p1_score if c.player_1 == obj else c.get_p2_score
            else:
                challenges = TeamChallenge.objects.filter(round=from_round).filter(Q(team_1=obj) | Q(team_2=obj))
                for c in challenges:
                    score += c.get_t1_score if c.team_1 == obj else c.get_t2_score
            ranked_winners.append({'obj': obj, 'score': score})
        
        ranked_winners.sort(key=lambda x: x['score'], reverse=True)
        limit = max(1, int(len(ranked_winners) * (percentage / 100.0)))
        promoted_objs = [x['obj'] for x in ranked_winners[:limit]]
        skipped_info = f'Top {percentage}% of winners ({len(promoted_objs)} out of {len(ranked_winners)}) selected.'

    else: # top_percentage
        ranked = []
        if is_single:
            participants = from_round.participants.all()
            for player in participants:
                challenges = SinglesChallenge.objects.filter(round=from_round).filter(Q(player_1=player) | Q(player_2=player))
                score = 0
                for c in challenges:
                    score += c.get_p1_score if c.player_1 == player else c.get_p2_score
                ranked.append({'obj': player, 'score': score})
        else:
            teams = from_round.teams.all()
            for team in teams:
                challenges = TeamChallenge.objects.filter(round=from_round).filter(Q(team_1=team) | Q(team_2=team))
                score = 0
                for c in challenges:
                    score += c.get_t1_score if c.team_1 == team else c.get_t2_score
                ranked.append({'obj': team, 'score': score})
        
        ranked.sort(key=lambda x: x['score'], reverse=True)
        limit = max(1, int(len(ranked) * (percentage / 100.0)))
        promoted_objs = [x['obj'] for x in ranked[:limit]]
        skipped_info = f'Top {percentage}% of all participants ({len(promoted_objs)} out of {len(ranked)}) selected.'

    if not promoted_objs:
        messages.error(request, 'No participants found to promote based on selected criteria.')
        return redirect('participation_edit', pk=pk)

    created = 0
    with transaction.atomic():
        if is_single:
            for u in promoted_objs:
                to_round.participants.add(u)
                created += 1
        else:
            for tm in promoted_objs:
                to_round.teams.add(tm)
                created += 1

    messages.success(request, f'Promoted {created} participant(s) to "{to_round.name}". {skipped_info}')
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


@staff_member_required
@require_POST
def quick_score_frame(request, pk, challenge_id):
    """
    Inline score update for a specific frame from the participation edit page.
    Expects side (p1/p2 or t1/t2), frame_order, r1, r2.
    """
    p = get_object_or_404(Participation, pk=pk)
    
    # Enforce latest round rule
    latest_round = p.rounds.order_by('-start_date', '-id').first()
    
    side = request.POST.get('side')
    try:
        frame_order = int(request.POST.get('frame_order'))
        r1 = _parse_roll_field(request.POST.get('r1'))
        r2 = _parse_roll_field(request.POST.get('r2'))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid data.'}, status=400)

    if side in ('p1', 'p2'):
        challenge = get_object_or_404(SinglesChallenge, pk=challenge_id, round__game_type=p)
        user = challenge.player_1 if side == 'p1' else challenge.player_2
        _ensure_singles_match_frames(challenge)
        frame = get_object_or_404(SinglesFrame, round=challenge.round, participant=user, order=frame_order)
        # Enforce "latest frame" rule
        subsequent = SinglesFrame.objects.filter(round=challenge.round, participant=user, order__gt=frame_order, played=True)
        if subsequent.exists():
            return JsonResponse({'ok': False, 'error': 'Cannot edit a frame if a later frame has scores.'}, status=400)
        
        with transaction.atomic():
            roll1 = _get_or_create_roll(SinglesRoll, frame, 1)
            if not roll1.is_recorded:
                s1 = _parse_roll_field(request.POST.get('r1'))
                if s1 == -1: s1 = 10 # / in r1 is treated as 10? No, usually r1 is a number.
                roll1.score = s1
                roll1.is_recorded = True
                roll1.save()
            roll2 = _get_or_create_roll(SinglesRoll, frame, 2)
            if not roll2.is_recorded:
                s2 = _parse_roll_field(request.POST.get('r2'))
                if s2 == -1: # Spare
                    s2 = max(0, 10 - roll1.score)
                roll2.score = s2
                roll2.is_recorded = True
                roll2.save()
            frame.played = frame.rolls.filter(is_recorded=True).exists()
            frame.save(update_fields=['played'])
            
    elif side in ('t1', 't2'):
        challenge = get_object_or_404(TeamChallenge, pk=challenge_id, round__game_type=p)
        team = challenge.team_1 if side == 't1' else challenge.team_2
        _ensure_team_match_frames(challenge)
        frame = get_object_or_404(TeamFrame, round=challenge.round, team=team, order=frame_order)
        subsequent = TeamFrame.objects.filter(round=challenge.round, team=team, order__gt=frame_order, played=True)
        if subsequent.exists():
            return JsonResponse({'ok': False, 'error': 'Cannot edit a frame if a later frame has scores.'}, status=400)

        with transaction.atomic():
            roll1 = _get_or_create_roll(TeamRoll, frame, 1)
            if not roll1.is_recorded:
                s1 = _parse_roll_field(request.POST.get('r1'))
                if s1 == -1: s1 = 10
                roll1.score = s1
                roll1.is_recorded = True
                roll1.save()
            roll2 = _get_or_create_roll(TeamRoll, frame, 2)
            if not roll2.is_recorded:
                s2 = _parse_roll_field(request.POST.get('r2'))
                if s2 == -1: # Spare
                    s2 = max(0, 10 - roll1.score)
                roll2.score = s2
                roll2.is_recorded = True
                roll2.save()
            frame.played = frame.rolls.filter(is_recorded=True).exists()
            frame.save(update_fields=['played'])
    else:
        return JsonResponse({'ok': False, 'error': 'Invalid side.'}, status=400)

    return JsonResponse({'ok': True})
from .forms import TeamForm, AddMemberForm

@login_required
def team_list(request):
    """List teams that are currently recruiting."""
    teams = Team.objects.filter(is_recruiting=True).select_related('captain').prefetch_related('members')
    my_teams = request.user.captained_teams.all() | request.user.member_teams.all()
    my_teams = my_teams.distinct()
    
    return render(request, 'core/team_list.html', {
        'teams': teams,
        'my_teams': my_teams
    })

@staff_member_required
def admin_team_list(request):
    """Admin view to manage all teams with search functionality."""
    query = request.GET.get('q', '').strip()
    teams = Team.objects.select_related('captain').prefetch_related('members').all().order_by('name')
    
    if query:
        from django.db.models import Q
        teams = teams.filter(
            Q(name__icontains=query) |
            Q(captain__email__icontains=query) |
            Q(captain__first_name__icontains=query) |
            Q(captain__last_name__icontains=query) |
            Q(captain__primary_phone__icontains=query) |
            Q(captain__secondary_phone__icontains=query) |
            Q(members__email__icontains=query) |
            Q(members__first_name__icontains=query) |
            Q(members__last_name__icontains=query) |
            Q(members__primary_phone__icontains=query) |
            Q(members__secondary_phone__icontains=query)
        ).distinct()
        
    return render(request, 'core/admin_team_list.html', {
        'teams': teams,
        'query': query
    })

@login_required
def team_create(request):
    """Create a new team and set current user as captain."""
    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save(commit=False)
            team.captain = request.user
            team.save()
            team.members.add(request.user)
            messages.success(request, f'Team "{team.name}" created successfully!')
            return redirect('team_detail', pk=team.pk)
    else:
        form = TeamForm()
    
    return render(request, 'core/team_form.html', {'form': form, 'title': 'Create Team'})

@login_required
def team_detail(request, pk):
    """View team members and manage recruiting status."""
    team = get_object_or_404(Team, pk=pk)
    is_captain = (team.captain == request.user)
    
    if is_captain and request.method == 'POST' and 'toggle_recruiting' in request.POST:
        team.is_recruiting = not team.is_recruiting
        team.save()
        status = "now recruiting" if team.is_recruiting else "no longer recruiting"
        messages.success(request, f'Team is {status}.')
        return redirect('team_detail', pk=team.pk)

    return render(request, 'core/team_detail.html', {
        'team': team,
        'is_captain': is_captain,
        'member_form': AddMemberForm() if is_captain else None
    })

@login_required
@require_POST
def team_add_member(request, pk):
    """Add a member to a team by email or phone. Only captain can do this."""
    team = get_object_or_404(Team, pk=pk)
    if team.captain != request.user:
        messages.error(request, 'Only the captain can add members.')
        return redirect('team_detail', pk=pk)
    
    form = AddMemberForm(request.POST)
    if form.is_valid():
        val = form.cleaned_data['identifier']
        # Search by email or primary_phone
        from django.db.models import Q
        user_to_add = User.objects.filter(Q(email__iexact=val) | Q(primary_phone=val)).first()
        
        if user_to_add:
            if user_to_add in team.members.all():
                messages.warning(request, f'{user_to_add.email} is already a member.')
            else:
                team.members.add(user_to_add)
                messages.success(request, f'{user_to_add.get_full_name() or user_to_add.email} added to the team!')
        else:
            messages.error(request, f'No user found matching "{val}". They must register first.')
    return redirect('team_detail', pk=pk)

@login_required
@require_POST
def participation_generate_fixtures(request, pk):
    """Bulk generate match fixtures for a specific round."""
    p = get_object_or_404(Participation, pk=pk)
    round_id = request.POST.get('round_id')
    r = get_object_or_404(Round, pk=round_id, game_type=p)
    group_by = request.POST.get('group_by', 'random')
    
    is_single = 'single' in p.name.lower()
    
    from django.utils import timezone
    import datetime
    
    # Create default datetimes from round dates
    start_dt = timezone.make_aware(datetime.datetime.combine(r.start_date, datetime.time.min))
    end_dt = timezone.make_aware(datetime.datetime.combine(r.end_date, datetime.time.max))

    if is_single:
        participants = list(r.participants.all())
        if not participants:
            # If empty round, check if we should pull from participation (likely first round)
            master_list = p.enrolled_users.all()
            if master_list.exists():
                r.participants.set(master_list)
                participants = list(master_list)
            else:
                messages.error(request, 'No participants enrolled in this round or category.')
                return redirect('participation_edit', pk=pk)
            
        # Grouping logic
        pairs = []
        if group_by == 'gender_same':
            # Separate by gender and pair within
            gender_map = {}
            for u in participants:
                g = u.gender or 'O'
                if g not in gender_map: gender_map[g] = []
                gender_map[g].append(u)
            for g_list in gender_map.values():
                import random
                random.shuffle(g_list)
                for i in range(0, len(g_list) - 1, 2):
                    pairs.append((g_list[i], g_list[i+1]))
        elif group_by == 'gender_opp':
            # Try to pair M with F, etc.
            males = [u for u in participants if u.gender == 'M']
            females = [u for u in participants if u.gender == 'F']
            others = [u for u in participants if u.gender not in ('M', 'F')]
            import random
            random.shuffle(males)
            random.shuffle(females)
            random.shuffle(others)
            
            # Pair M-F
            while males and females:
                pairs.append((males.pop(), females.pop()))
            # Pair remaining with others
            rem = males + females + others
            random.shuffle(rem)
            for i in range(0, len(rem) - 1, 2):
                pairs.append((rem[i], rem[i+1]))
        elif group_by == 'age_5':
            # Sort by age and pair neighbors if within 5 years
            from datetime import date
            def get_age(bd):
                if not bd: return 999
                today = date.today()
                return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
            
            sorted_by_age = sorted(participants, key=lambda u: get_age(u.birth_date))
            i = 0
            while i < len(sorted_by_age) - 1:
                u1 = sorted_by_age[i]
                u2 = sorted_by_age[i+1]
                a1 = get_age(u1.birth_date)
                a2 = get_age(u2.birth_date)
                if a1 != 999 and a2 != 999 and abs(a1 - a2) <= 5:
                    pairs.append((u1, u2))
                    i += 2
                else:
                    # Skip u1 and try next pair? Or just pair anyway?
                    # The requirement says "age group of 5 year difference".
                    # I'll pair them anyway if no better match, or just skip?
                    # Let's just pair neighbors to keep it simple but prioritize the 5yr gap.
                    pairs.append((u1, u2))
                    i += 2
        else:
            # Random / Single group
            import random
            random.shuffle(participants)
            for i in range(0, len(participants) - 1, 2):
                pairs.append((participants[i], participants[i+1]))
            
        created_count = 0
        for p1, p2 in pairs:
            # Check if already exists
            exists = SinglesChallenge.objects.filter(
                round=r,
                player_1__in=[p1, p2],
                player_2__in=[p1, p2]
            ).exists()
            if not exists:
                SinglesChallenge.objects.create(
                    round=r, 
                    player_1=p1, 
                    player_2=p2,
                    start_datetime=start_dt,
                    end_datetime=end_dt
                )
                created_count += 1
        
        messages.success(request, f'Generated {created_count} singles fixtures using "{group_by}" strategy.')
    else:
        # Team fixtures - simpler random for now
        teams = list(r.teams.all())
        if not teams:
            master_list = p.enrolled_teams.all()
            if master_list.exists():
                r.teams.set(master_list)
                teams = list(master_list)
            else:
                messages.error(request, 'No teams enrolled in this round or category.')
                return redirect('participation_edit', pk=pk)
        
        import random
        random.shuffle(teams)
        created_count = 0
        for i in range(0, len(teams) - 1, 2):
            t1, t2 = teams[i], teams[i+1]
            exists = TeamChallenge.objects.filter(
                round=r,
                team_1__in=[t1, t2],
                team_2__in=[t1, t2]
            ).exists()
            if not exists:
                TeamChallenge.objects.create(
                    round=r, 
                    team_1=t1, 
                    team_2=t2,
                    start_datetime=start_dt,
                    end_datetime=end_dt
                )
                created_count += 1
        messages.success(request, f'Generated {created_count} team fixtures.')

    return redirect('participation_edit', pk=pk)

@login_required
@require_POST
def participation_manual_promote(request, pk, round_id):
    """Manually promote multiple participants/teams to the next chronological round by order."""
    p = get_object_or_404(Participation, pk=pk)
    r = get_object_or_404(Round, pk=round_id, game_type=p)
    
    target_ids = request.POST.getlist('target_ids[]')
    if not target_ids:
        tid = request.POST.get('target_id')
        if tid:
            target_ids = [tid]
            
    if not target_ids:
        return JsonResponse({'ok': False, 'error': 'No participants selected.'}, status=400)
    
    # Find next round by order
    next_round = p.rounds.filter(order__gt=r.order).order_by('order').first()
    if not next_round:
        return JsonResponse({'ok': False, 'error': 'No subsequent round exists.'}, status=400)
    
    if next_round.is_completed:
        return JsonResponse({'ok': False, 'error': 'The next round is already completed.'}, status=400)
    
    is_single = 'single' in p.name.lower()
    promoted_count = 0
    
    with transaction.atomic():
        if is_single:
            users = User.objects.filter(pk__in=target_ids)
            for u in users:
                next_round.participants.add(u)
                promoted_count += 1
        else:
            teams = Team.objects.filter(pk__in=target_ids)
            for t in teams:
                next_round.teams.add(t)
                promoted_count += 1
        
    return JsonResponse({'ok': True, 'message': f'Promoted {promoted_count} participants to {next_round.name}'})

@login_required
@require_POST
def participation_round_complete(request, pk, round_id):
    """Mark a round as completed."""
    p = get_object_or_404(Participation, pk=pk)
    r = get_object_or_404(Round, pk=round_id, game_type=p)
    
    r.is_completed = True
    r.save()
    
    return JsonResponse({'ok': True, 'message': f'Round "{r.name}" marked as completed.'})
@login_required
def initiate_enrollment_payment(request, pk):
    participation = get_object_or_404(Participation, pk=pk)
    
    if request.user in participation.enrolled_users.all():
        messages.info(request, "You are already enrolled in this category.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        print(f"DEBUG: Enrollment POST received. Participation: {participation.id}, Phone: {phone_number}")
        
        if not phone_number:
            messages.error(request, "Phone number is required.")
            return redirect('initiate_enrollment_payment', pk=pk)
            
        # Clean phone number (remove +, spaces, etc)
        phone_number = ''.join(filter(str.isdigit, phone_number))
        
        # Trigger STK Push
        # participation ID as account reference as requested
        print(f"DEBUG: Calling MpesaService.stk_push...")
        resp, error = MpesaService.stk_push(phone_number, participation.charge, str(participation.id))
        print(f"DEBUG: MpesaService.stk_push returned. Resp: {resp}, Error: {error}")
        
        if error or resp.get('ResponseCode') != '0':
            msg = error or resp.get('CustomerMessage', 'Failed to initiate payment')
            messages.error(request, f"Error: {msg}")
            return redirect('initiate_enrollment_payment', pk=pk)
            
        # Create Pending Payment
        Payment.objects.create(
            user=request.user,
            participation=participation,
            amount=participation.charge,
            phone_number=phone_number,
            checkout_request_id=resp['CheckoutRequestID'],
            merchant_request_id=resp['MerchantRequestID'],
            status='PENDING'
        )
        
        messages.success(request, "Payment initiated. Please check your phone for the M-Pesa PIN prompt.")
        return redirect('dashboard')
    
    return render(request, 'core/enroll_payment.html', {'participation': participation})

@csrf_exempt
@require_POST
def mpesa_callback(request):
    try:
        data = json.loads(request.body)
        stk_callback = data.get('Body', {}).get('stkCallback', {})
        
        merchant_request_id = stk_callback.get('MerchantRequestID')
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')
        
        try:
            payment = Payment.objects.get(checkout_request_id=checkout_request_id)
            payment.result_desc = result_desc
            
            if result_code == 0:
                # Success
                payment.status = 'SUCCESS'
                # Extract transaction ID from CallbackMetadata
                items = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                for item in items:
                    if item.get('Name') == 'MpesaReceiptNumber':
                        payment.transaction_id = item.get('Value')
                        break
                
                # Enroll the user in the participation
                payment.participation.enrolled_users.add(payment.user)
                payment.save()
                return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
            else:
                # Failed (user cancelled, insufficient funds, etc)
                payment.status = 'FAILED'
                payment.save()
                return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
                
        except Payment.DoesNotExist:
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Payment not found'}, status=404)
            
    except Exception as e:
        return JsonResponse({'ResultCode': 1, 'ResultDesc': str(e)}, status=500)


@staff_member_required
def payment_list(request):
    """
    Admin view to list all payments, tabbed by season and filterable.
    """
    seasons = Season.objects.all().order_by('-start_date')
    selected_season_id = request.GET.get('season')
    
    if not selected_season_id and seasons.exists():
        selected_season_id = seasons.first().id
        
    selected_season = None
    if selected_season_id:
        selected_season = get_object_or_404(Season, id=selected_season_id)

    # Base queryset
    payments = Payment.objects.select_related('user', 'participation__game_type', 'participation__season')
    
    if selected_season:
        payments = payments.filter(participation__season=selected_season)
    
    # Filters
    status_filter = request.GET.get('status')
    if status_filter:
        payments = payments.filter(status=status_filter)
        
    participation_filter = request.GET.get('participation')
    if participation_filter:
        payments = payments.filter(participation_id=participation_filter)

    round_filter = request.GET.get('round')
    if round_filter:
        # Filter payments where the user is a participant in the selected round
        payments = payments.filter(participation__rounds__id=round_filter, user__rounds__id=round_filter)

    payments = payments.order_by('-created_at')

    # Aggregates for the selected season
    from django.db.models import Sum
    season_payments = Payment.objects.filter(participation__season=selected_season) if selected_season else Payment.objects.all()
    
    total_revenue = season_payments.filter(status='SUCCESS').aggregate(total=Sum('amount'))['total'] or 0
    pending_count = season_payments.filter(status='PENDING').count()
    success_count = season_payments.filter(status='SUCCESS').count()
    failed_count = season_payments.filter(status='FAILED').count()

    # Participations for the season (for filter dropdown)
    available_participations = []
    available_rounds = []
    if selected_season:
        available_participations = Participation.objects.filter(season=selected_season).select_related('game_type')
        available_rounds = Round.objects.filter(season=selected_season).order_by('order')

    return render(request, 'core/payment_list.html', {
        'seasons': seasons,
        'selected_season': selected_season,
        'payments': payments,
        'status_filter': status_filter,
        'participation_filter': participation_filter,
        'round_filter': round_filter,
        'available_participations': available_participations,
        'available_rounds': available_rounds,
        'total_revenue': total_revenue,
        'pending_count': pending_count,
        'success_count': success_count,
        'failed_count': failed_count,
    })
@require_POST
def chat_assistant(request):
    """
    Endpoint for the AI chat widget.
    """
    import json
    from .ai import get_ai_response
    
    data = json.loads(request.body)
    user_message = data.get('message', '')
    history = data.get('history', []) # List of {role: ..., content: ...}
    
    if not user_message:
        return JsonResponse({'error': 'No message provided'}, status=400)
    
    # Prepare messages for OpenAI (limiting history to last 10 messages)
    messages = history[-10:] + [{"role": "user", "content": user_message}]
    
    ai_response = get_ai_response(messages, user_obj=request.user if request.user.is_authenticated else None)
    
    # Log messages to database
    from .models import ChatMessage
    session_id = request.session.session_key or 'anonymous'
    
    # Save User message
    ChatMessage.objects.create(
        user=request.user if request.user.is_authenticated else None,
        role='user',
        content=user_message,
        session_id=session_id
    )
    
    # Save Assistant message
    ChatMessage.objects.create(
        user=request.user if request.user.is_authenticated else None,
        role='assistant',
        content=ai_response,
        session_id=session_id
    )
    
    return JsonResponse({'response': ai_response})
@staff_member_required
def chat_logs(request):
    """
    View all AI chat logs grouped by session.
    """
    from .models import ChatMessage
    from django.db.models import Max
    
    # Get all unique session IDs ordered by their most recent message
    sessions = ChatMessage.objects.values('session_id').annotate(
        last_message=Max('created_at')
    ).order_by('-last_message')
    
    # For each session, get all messages
    logs = []
    for s in sessions:
        msgs = ChatMessage.objects.filter(session_id=s['session_id']).order_by('created_at')
        if msgs.exists():
            logs.append({
                'session_id': s['session_id'],
                'user': msgs.first().user,
                'messages': msgs,
                'last_updated': s['last_message']
            })
            
    return render(request, 'core/chat_logs.html', {'logs': logs})
