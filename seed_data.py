import os
import django
import random
from datetime import timedelta
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bowling.settings')
django.setup()

from core.models import (
    User, Team, Season, GameType, Participation, Round,
    SinglesChallenge, TeamChallenge, SinglesFrame, TeamFrame, SinglesRoll, TeamRoll
)

def create_fake_data():
    print("Deleting old data...")
    SinglesRoll.objects.all().delete()
    TeamRoll.objects.all().delete()
    SinglesFrame.objects.all().delete()
    TeamFrame.objects.all().delete()
    SinglesChallenge.objects.all().delete()
    TeamChallenge.objects.all().delete()
    Round.objects.all().delete()
    Participation.objects.all().delete()
    GameType.objects.all().delete()
    Season.objects.all().delete()
    Team.objects.all().delete()
    User.objects.filter(is_superuser=False).delete()

    print("Creating 100 Users...")
    from django.contrib.auth.hashers import make_password
    default_password = make_password("1234")
    
    users = []
    for i in range(1, 101):
        email = f"player{i}@example.com"
        u = User(email=email, first_name="Player", last_name=f"{i}", primary_phone=f"555-010{i:02d}", password=default_password)
        users.append(u)
    User.objects.bulk_create(users)
    users = list(User.objects.filter(is_superuser=False))

    print("Creating 10 Teams...")
    teams = []
    team_categories = ['Double', 'Trio', 'Four']
    
    # We have 100 users, let's just pick distinct ones for captains and members
    shuffled_users = list(users)
    random.shuffle(shuffled_users)
    
    for i in range(10):
        cat = random.choice(team_categories)
        captain = shuffled_users.pop()
        t = Team.objects.create(name=f"Strikers {i+1}", captain=captain, category=cat, is_recruiting=False)
        
        # Add members based on category
        members_needed = 1 if cat == 'Double' else (2 if cat == 'Trio' else 3)
        for _ in range(members_needed):
            if shuffled_users:
                t.members.add(shuffled_users.pop())
        teams.append(t)

    print("Creating Season & Game Type...")
    now = timezone.now()
    season = Season.objects.create(
        name="Summer Invitational 2026",
        start_date=now.date() - timedelta(days=30),
        end_date=now.date() + timedelta(days=60),
        is_active=True,
        register_start_date=now.date() - timedelta(days=60),
        register_end_date=now.date() - timedelta(days=31)
    )
    season.participants.set(users)
    season.teams.set(teams)

    gt = GameType.objects.create(name="10-Pin Standard", description="Classic 10-Pin Bowling")

    part_single = Participation.objects.create(season=season, game_type=gt, name="Single", charge=25.00)
    part_team = Participation.objects.create(season=season, game_type=gt, name="Four", charge=80.00)

    print("Creating Rounds and Challenges...")
    # 4 Rounds for Singles
    singles_rounds = []
    for i in range(1, 5):
        r = Round.objects.create(
            name=f"Singles Round {i}", season=season, game_type=part_single,
            start_date=season.start_date + timedelta(days=i*7),
            end_date=season.start_date + timedelta(days=i*7 + 6)
        )
        r.participants.set(users)
        singles_rounds.append(r)

    # 4 Rounds for Teams
    teams_rounds = []
    for i in range(1, 5):
        r = Round.objects.create(
            name=f"Teams Round {i}", season=season, game_type=part_team,
            start_date=season.start_date + timedelta(days=i*7),
            end_date=season.start_date + timedelta(days=i*7 + 6)
        )
        r.teams.set(teams)
        teams_rounds.append(r)

    print("Creating Fixtures & Scores...")
    # Helper to generate 10 frames for a participant
    from django.db import transaction

    @transaction.atomic
    def generate_frames_and_rolls(participant, round_obj, is_team=False):
        for f_idx in range(1, 11):
            if is_team:
                frame = TeamFrame.objects.create(order=f_idx, participant=participant.captain, round=round_obj, team=participant, played=True)
            else:
                frame = SinglesFrame.objects.create(order=f_idx, participant=participant, round=round_obj, played=True)

            roll1_score = random.randint(0, 10)
            roll2_score = random.randint(0, 10 - roll1_score) if roll1_score < 10 else 0
            
            if is_team:
                TeamRoll.objects.create(frame=frame, order=1, score=roll1_score)
                if roll1_score < 10:
                    TeamRoll.objects.create(frame=frame, order=2, score=roll2_score)
            else:
                SinglesRoll.objects.create(frame=frame, order=1, score=roll1_score)
                if roll1_score < 10:
                    SinglesRoll.objects.create(frame=frame, order=2, score=roll2_score)

    print("Generating singles challenges and scores...")
    with transaction.atomic():
        for r in singles_rounds:
            shuffled = list(users)
            random.shuffle(shuffled)
            
            challenges = []
            for i in range(0, 100, 2):
                p1 = shuffled[i]
                p2 = shuffled[i+1]
                challenges.append(SinglesChallenge(
                    round=r, player_1=p1, player_2=p2,
                    start_datetime=now, end_datetime=now + timedelta(hours=1)
                ))
                generate_frames_and_rolls(p1, r, is_team=False)
                generate_frames_and_rolls(p2, r, is_team=False)
                
            SinglesChallenge.objects.bulk_create(challenges)

    print("Generating team challenges and scores...")
    with transaction.atomic():
        for r in teams_rounds:
            shuffled = list(teams)
            random.shuffle(shuffled)
            
            challenges = []
            for i in range(0, 10, 2):
                t1 = shuffled[i]
                t2 = shuffled[i+1]
                challenges.append(TeamChallenge(
                    round=r, team_1=t1, team_2=t2,
                    start_datetime=now, end_datetime=now + timedelta(hours=1)
                ))
                generate_frames_and_rolls(t1, r, is_team=True)
                generate_frames_and_rolls(t2, r, is_team=True)
                
            TeamChallenge.objects.bulk_create(challenges)

    print("Successfully generated fake data!")

if __name__ == '__main__':
    create_fake_data()
