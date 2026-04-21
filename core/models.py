from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _

class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifiers
    for authentication instead of usernames.
    """
    def create_user(self, email, password, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None
    email = models.EmailField(_('email address'), unique=True)
    
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    primary_phone = models.CharField(max_length=20, blank=True, null=True)
    secondary_phone = models.CharField(max_length=20, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email


class Team(models.Model):
    choices = [
        ('Double', 'Double'),
        ('Trio', 'Trio'),
        ('Four', 'Four'),
    ]
    name = models.CharField(max_length=100)
    captain = models.ForeignKey(User, on_delete=models.CASCADE, related_name='captained_teams')
    members = models.ManyToManyField(User, related_name='member_teams')
    category = models.CharField(max_length=100, choices=choices)
    is_recruiting = models.BooleanField(default=False)
    def __str__(self):
        return self.name

class Season(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    register_start_date = models.DateField()
    register_end_date = models.DateField()
    participants = models.ManyToManyField(User, related_name='participants')
    teams = models.ManyToManyField(Team, related_name='teamups')
    hero_image = models.URLField(blank=True, null=True, help_text="URL for the hero background image")
    
    def __str__(self):
        return self.name

class SeasonSchedule(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='schedules')
    event = models.CharField(max_length=100)
    date_range = models.CharField(max_length=100)
    details = models.TextField()
    order = models.IntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.season.name} - {self.event}"


class GameType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    def __str__(self):
        return self.name


    
class Participation(models.Model):
    choices = [
        ('Single', 'Single'),
        ('Double', 'Double'),
        ('Trio', 'Trio'),
    ]
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='participations')
    game_type = models.ForeignKey(GameType, on_delete=models.CASCADE, related_name='participations')
    name = models.CharField(max_length=100, choices=choices)
    charge = models.DecimalField(max_digits=10, decimal_places=2)
    enrolled_users = models.ManyToManyField(User, related_name='enrolled_participations', blank=True)
    enrolled_teams = models.ManyToManyField(Team, related_name='enrolled_participations', blank=True)
    
    def __str__(self):
        return f"{self.name} - {self.season.name} - {self.game_type.name}"

    class Meta:
        verbose_name_plural = 'Participations'
        unique_together = ('season', 'game_type', 'name')
class Round(models.Model):
    name = models.CharField(max_length=100)
    order = models.IntegerField()
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='rounds')
    participants = models.ManyToManyField(User, related_name='rounds')
    teams = models.ManyToManyField(Team, related_name='team_rounds')
    start_date = models.DateField()
    end_date = models.DateField()
    game_type = models.ForeignKey(Participation, on_delete=models.CASCADE, related_name='rounds')
    is_completed = models.BooleanField(default=False)


    def __str__(self):
        return f"{self.name} - {self.season.name}"

class GameRules(models.Model):
    game_type = models.ForeignKey(Participation, on_delete=models.CASCADE, related_name='rules')
    rules = models.TextField()
    order = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.game_type.name} rules - {self.order}"

class SinglesChallenge(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='singles_challenges')
    player_1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='singles_challenges_1')
    player_2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='singles_challenges_2')
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    
    @property
    def get_p1_score(self):
        from django.db.models import Sum
        res = SinglesRoll.objects.filter(frame__round=self.round, frame__participant=self.player_1).aggregate(total=Sum('score'))
        return res['total'] or 0

    @property
    def get_p2_score(self):
        from django.db.models import Sum
        res = SinglesRoll.objects.filter(frame__round=self.round, frame__participant=self.player_2).aggregate(total=Sum('score'))
        return res['total'] or 0

    @property
    def get_p1_frame_scores(self):
        from django.db.models import Sum
        frames = SinglesFrame.objects.filter(round=self.round, participant=self.player_1).order_by('order').annotate(total=Sum('rolls__score'))
        return [f.total or 0 for f in frames]

    @property
    def get_p2_frame_scores(self):
        from django.db.models import Sum
        frames = SinglesFrame.objects.filter(round=self.round, participant=self.player_2).order_by('order').annotate(total=Sum('rolls__score'))
        return [f.total or 0 for f in frames]

    def get_frame_score_rows(self):
        """
        Returns list of frame info including roll scores and recorded status.
        """
        f1 = list(SinglesFrame.objects.filter(round=self.round, participant=self.player_1).order_by('order'))
        f2 = list(SinglesFrame.objects.filter(round=self.round, participant=self.player_2).order_by('order'))
        
        n = 10
        rows = []
        for i in range(n):
            order = i + 1
            
            # P1 info
            p1_r1 = p1_r2 = 0
            p1_r1_recorded = p1_r2_recorded = False
            if i < len(f1):
                rolls = {r.order: r for r in f1[i].rolls.all()}
                r1 = rolls.get(1)
                if r1:
                    p1_r1 = r1.score
                    p1_r1_recorded = r1.is_recorded
                r2 = rolls.get(2)
                if r2:
                    p1_r2 = r2.score
                    p1_r2_recorded = r2.is_recorded
            
            # P2 info
            p2_r1 = p2_r2 = 0
            p2_r1_recorded = p2_r2_recorded = False
            if i < len(f2):
                rolls = {r.order: r for r in f2[i].rolls.all()}
                r1 = rolls.get(1)
                if r1:
                    p2_r1 = r1.score
                    p2_r1_recorded = r1.is_recorded
                r2 = rolls.get(2)
                if r2:
                    p2_r2 = r2.score
                    p2_r2_recorded = r2.is_recorded
            
            # Display logic
            def format_score(r1, r2):
                if r1 == 10:
                    return "X"
                if (r1 or 0) + (r2 or 0) == 10:
                    return f"{r1} /"
                if r1 == 0 and r2 == 0:
                    return "—"
                return f"{r1} {r2}"

            rows.append({
                'order': order,
                'p1_r1': p1_r1,
                'p1_r1_recorded': p1_r1_recorded,
                'p1_r2': p1_r2,
                'p1_r2_recorded': p1_r2_recorded,
                'p1_total': p1_r1 + p1_r2,
                'p1_display': format_score(p1_r1, p1_r2),
                'p2_r1': p2_r1,
                'p2_r1_recorded': p2_r1_recorded,
                'p2_r2': p2_r2,
                'p2_r2_recorded': p2_r2_recorded,
                'p2_total': p2_r1 + p2_r2,
                'p2_display': format_score(p2_r1, p2_r2),
                'p1_editable': not p1_r1_recorded or not p1_r2_recorded,
                'p2_editable': not p2_r1_recorded or not p2_r2_recorded,
            })
        return rows

    def get_winner_label(self):
        """Display name of higher total, 'Tie', or None if no scores yet."""
        total1 = self.get_p1_score
        total2 = self.get_p2_score
        n1 = (self.player_1.get_full_name() or "").strip() or self.player_1.email
        n2 = (self.player_2.get_full_name() or "").strip() or self.player_2.email
        if total1 > total2:
            return n1
        if total2 > total1:
            return n2
        if total1 == 0 and total2 == 0:
            return None
        return "Tie"

    def get_winner_player(self):
        """Winning User, or None if unplayed or tied."""
        total1 = self.get_p1_score
        total2 = self.get_p2_score
        if total1 == 0 and total2 == 0:
            return None
        if total1 > total2:
            return self.player_1
        if total2 > total1:
            return self.player_2
        return None
    def get_next_p1_frame(self):
        frames = list(SinglesFrame.objects.filter(round=self.round, participant=self.player_1).order_by('order'))
        for i, f in enumerate(frames):
            if not f.played:
                # Check if all subsequent frames are also unplayed
                if all(not next_f.played for next_f in frames[i+1:]):
                    return f
                return None
        return None

    def get_next_p2_frame(self):
        frames = list(SinglesFrame.objects.filter(round=self.round, participant=self.player_2).order_by('order'))
        for i, f in enumerate(frames):
            if not f.played:
                if all(not next_f.played for next_f in frames[i+1:]):
                    return f
                return None
        return None

class TeamChallenge(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='team_challenges')
    team_1 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='team_challenges_1')
    team_2 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='team_challenges_2')
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    @property
    def get_t1_score(self):
        from django.db.models import Sum
        res = TeamRoll.objects.filter(frame__round=self.round, frame__team=self.team_1).aggregate(total=Sum('score'))
        return res['total'] or 0

    @property
    def get_t2_score(self):
        from django.db.models import Sum
        res = TeamRoll.objects.filter(frame__round=self.round, frame__team=self.team_2).aggregate(total=Sum('score'))
        return res['total'] or 0

    @property
    def get_t1_frame_scores(self):
        from django.db.models import Sum
        frames = TeamFrame.objects.filter(round=self.round, team=self.team_1).order_by('order').annotate(total=Sum('rolls__score'))
        return [f.total or 0 for f in frames]

    @property
    def get_t2_frame_scores(self):
        from django.db.models import Sum
        frames = TeamFrame.objects.filter(round=self.round, team=self.team_2).order_by('order').annotate(total=Sum('rolls__score'))
        return [f.total or 0 for f in frames]

    def get_frame_score_rows(self):
        """
        Returns list of frame info including roll scores and recorded status.
        """
        f1 = list(TeamFrame.objects.filter(round=self.round, team=self.team_1).order_by('order'))
        f2 = list(TeamFrame.objects.filter(round=self.round, team=self.team_2).order_by('order'))
        
        n = 10
        rows = []
        for i in range(n):
            order = i + 1
            
            # T1 info
            t1_r1 = t1_r2 = 0
            t1_r1_recorded = t1_r2_recorded = False
            if i < len(f1):
                rolls = {r.order: r for r in f1[i].rolls.all()}
                r1 = rolls.get(1)
                if r1:
                    t1_r1 = r1.score
                    t1_r1_recorded = r1.is_recorded
                r2 = rolls.get(2)
                if r2:
                    t1_r2 = r2.score
                    t1_r2_recorded = r2.is_recorded
            
            # T2 info
            t2_r1 = t2_r2 = 0
            t2_r1_recorded = t2_r2_recorded = False
            if i < len(f2):
                rolls = {r.order: r for r in f2[i].rolls.all()}
                r1 = rolls.get(1)
                if r1:
                    t2_r1 = r1.score
                    t2_r1_recorded = r1.is_recorded
                r2 = rolls.get(2)
                if r2:
                    t2_r2 = r2.score
                    t2_r2_recorded = r2.is_recorded
            
            # Display logic
            def format_score(r1, r2):
                if r1 == 10:
                    return "X"
                if (r1 or 0) + (r2 or 0) == 10:
                    return f"{r1} /"
                if r1 == 0 and r2 == 0:
                    return "—"
                return f"{r1} {r2}"

            rows.append({
                'order': order,
                't1_r1': t1_r1,
                't1_r1_recorded': t1_r1_recorded,
                't1_r2': t1_r2,
                't1_r2_recorded': t1_r2_recorded,
                't1_total': t1_r1 + t1_r2,
                't1_display': format_score(t1_r1, t1_r2),
                't2_r1': t2_r1,
                't2_r1_recorded': t2_r1_recorded,
                't2_r2': t2_r2,
                't2_r2_recorded': t2_r2_recorded,
                't2_total': t2_r1 + t2_r2,
                't2_display': format_score(t2_r1, t2_r2),
                't1_editable': not t1_r1_recorded or not t1_r2_recorded,
                't2_editable': not t2_r1_recorded or not t2_r2_recorded,
            })
        return rows

    def get_winner_label(self):
        """Team name with higher total, 'Tie', or None if no scores yet."""
        total1 = self.get_t1_score
        total2 = self.get_t2_score
        if total1 > total2:
            return self.team_1.name
        if total2 > total1:
            return self.team_2.name
        if total1 == 0 and total2 == 0:
            return None
        return "Tie"

    def get_winner_team(self):
        """Winning Team instance, or None if unplayed or tied."""
        total1 = self.get_t1_score
        total2 = self.get_t2_score
        if total1 == 0 and total2 == 0:
            return None
        if total1 > total2:
            return self.team_1
        if total2 > total1:
            return self.team_2
        return None
    def get_next_t1_frame(self):
        frames = list(TeamFrame.objects.filter(round=self.round, team=self.team_1).order_by('order'))
        for i, f in enumerate(frames):
            if not f.played:
                if all(not next_f.played for next_f in frames[i+1:]):
                    return f
                return None
        return None

    def get_next_t2_frame(self):
        frames = list(TeamFrame.objects.filter(round=self.round, team=self.team_2).order_by('order'))
        for i, f in enumerate(frames):
            if not f.played:
                if all(not next_f.played for next_f in frames[i+1:]):
                    return f
                return None
        return None

class SinglesFrame(models.Model):
    order = models.IntegerField(default=0)
    participant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='singles_frames')
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='singles_frames')
    played = models.BooleanField(default=False)

class TeamFrame(models.Model):
    order = models.IntegerField(default=0)
    participant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_frames')
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='team_frames')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='team_frames') 
    played = models.BooleanField(default=False)


class SinglesRoll(models.Model):
    frame = models.ForeignKey(SinglesFrame, on_delete=models.CASCADE, related_name='rolls')
    order = models.IntegerField(default=0)
    score = models.IntegerField(default=0)
    is_recorded = models.BooleanField(default=False)
    
class TeamRoll(models.Model):
    frame = models.ForeignKey(TeamFrame, on_delete=models.CASCADE, related_name='rolls')
    order = models.IntegerField(default=0)
    score = models.IntegerField(default=0)
    is_recorded = models.BooleanField(default=False)


class Payment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    participation = models.ForeignKey(Participation, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    checkout_request_id = models.CharField(max_length=100, unique=True)
    merchant_request_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    result_desc = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.participation.name} - {self.status}"

class ChatMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_chats')
    role = models.CharField(max_length=20, choices=[('user', 'User'), ('assistant', 'Assistant')])
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=100, null=True, blank=True) # To group messages from same session

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."

class CustomerInquiry(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    phone_number = models.CharField(max_length=20)
    inquiry_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)

    def __str__(self):
        return f"Inquiry from {self.phone_number} on {self.created_at.date()}"
