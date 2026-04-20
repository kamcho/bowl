import os
import django
import random


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bowling.settings')
django.setup()

from core.models import Round, SinglesChallenge, SinglesFrame, SinglesRoll

def populate_scores(challenge):
    # Only populate if no frames exist or scores are all 0
    existing = SinglesFrame.objects.filter(round=challenge.round, participant=challenge.player_1)
    if existing.exists():
        # Check if they are all 0
        total = sum(r.score for f in existing for r in f.rolls.all())
        if total > 0:
            return # Already has data
    
    print(f"Populating scores for challenge {challenge.id}: {challenge.player_1} vs {challenge.player_2}")
    
    for player in [challenge.player_1, challenge.player_2]:
        SinglesFrame.objects.filter(round=challenge.round, participant=player).delete()
        
        for i in range(1, 11):
            frame = SinglesFrame.objects.create(round=challenge.round, participant=player, order=i, played=True)
            r1 = random.randint(0, 10)
            r2 = random.randint(0, 10 - r1)
            SinglesRoll.objects.create(frame=frame, order=1, score=r1, is_recorded=True)
            SinglesRoll.objects.create(frame=frame, order=2, score=r2, is_recorded=True)

def run():
    round_id = 83
    r = Round.objects.filter(id=round_id).first()
    if not r:
        print(f"Round {round_id} not found")
        return
    
    challenges = SinglesChallenge.objects.filter(round=r)
    for c in challenges:
        populate_scores(c)
    
    print("Successfully populated scores for remaining fixtures in Round 79.")

if __name__ == "__main__":
    run()
