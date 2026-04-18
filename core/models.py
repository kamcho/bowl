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
    def __str__(self):
        return self.name


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
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='rounds')
    participants = models.ManyToManyField(User, related_name='rounds')
    teams = models.ManyToManyField(Team, related_name='team_rounds')
    start_date = models.DateField()
    end_date = models.DateField()
    game_type = models.ForeignKey(Participation, on_delete=models.CASCADE, related_name='rounds')
    
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
        """(frame_number, player_1_pins, player_2_pins) for each frame."""
        s1 = self.get_p1_frame_scores
        s2 = self.get_p2_frame_scores
        n = max(len(s1), len(s2))
        rows = []
        for i in range(n):
            rows.append(
                (
                    i + 1,
                    s1[i] if i < len(s1) else None,
                    s2[i] if i < len(s2) else None,
                )
            )
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
        """(frame_number, team_1_pins, team_2_pins) for each frame."""
        s1 = self.get_t1_frame_scores
        s2 = self.get_t2_frame_scores
        n = max(len(s1), len(s2))
        rows = []
        for i in range(n):
            rows.append(
                (
                    i + 1,
                    s1[i] if i < len(s1) else None,
                    s2[i] if i < len(s2) else None,
                )
            )
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
    
class TeamRoll(models.Model):
    frame = models.ForeignKey(TeamFrame, on_delete=models.CASCADE, related_name='rolls')
    order = models.IntegerField(default=0)
    score = models.IntegerField(default=0)


