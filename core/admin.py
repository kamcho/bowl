from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Season, GameType, Participation, GameRules,
    Team, Round, SinglesChallenge, TeamChallenge,
    SinglesFrame, TeamFrame, SinglesRoll, TeamRoll,
    SeasonSchedule, CustomerInquiry, ChatMessage
)


class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ('email', 'first_name', 'last_name', 'gender', 'is_staff')
    list_filter = ('is_staff', 'is_active', 'gender')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'gender', 'primary_phone', 'secondary_phone')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(GameType)
class GameTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(SeasonSchedule)
class SeasonScheduleAdmin(admin.ModelAdmin):
    list_display = ('season', 'event', 'date_range', 'order')
    list_filter = ('season',)
    search_fields = ('event', 'date_range')


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ('name', 'season', 'game_type', 'charge')
    list_filter = ('name', 'season')
    search_fields = ('season__name', 'game_type__name')


@admin.register(GameRules)
class GameRulesAdmin(admin.ModelAdmin):
    list_display = ('game_type', 'order')
    list_filter = ('game_type',)
    ordering = ('game_type', 'order')


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'captain', 'category', 'is_recruiting')
    list_filter = ('category', 'is_recruiting')
    search_fields = ('name', 'captain__email', 'captain__first_name')


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('name', 'season', 'game_type', 'start_date', 'end_date', 'create_fixtures_link')
    list_filter = ('season', 'game_type')
    search_fields = ('name', 'season__name')

    def create_fixtures_link(self, obj):
        from django.utils.html import format_html
        from django.urls import reverse
        url = reverse('participation_edit', args=[obj.game_type.pk])
        return format_html('<a class="button" href="{}">Create Fixtures</a>', url)
    create_fixtures_link.short_description = "Actions"


@admin.register(SinglesChallenge)
class SinglesChallengeAdmin(admin.ModelAdmin):
    list_display = ('round', 'player_1', 'player_2', 'start_datetime')
    list_filter = ('round',)
    search_fields = ('player_1__email', 'player_2__email')


@admin.register(TeamChallenge)
class TeamChallengeAdmin(admin.ModelAdmin):
    list_display = ('round', 'team_1', 'team_2', 'start_datetime')
    list_filter = ('round',)
    search_fields = ('team_1__name', 'team_2__name')


@admin.register(SinglesFrame)
class SinglesFrameAdmin(admin.ModelAdmin):
    list_display = ('round', 'participant', 'order', 'played')
    list_filter = ('round', 'played')


@admin.register(TeamFrame)
class TeamFrameAdmin(admin.ModelAdmin):
    list_display = ('round', 'team', 'participant', 'order', 'played')
    list_filter = ('round', 'played', 'team')


@admin.register(SinglesRoll)
class SinglesRollAdmin(admin.ModelAdmin):
    list_display = ('frame', 'order', 'score')


@admin.register(TeamRoll)
class TeamRollAdmin(admin.ModelAdmin):
    list_display = ('frame', 'order', 'score')


admin.site.register(User, UserAdmin)

@admin.register(CustomerInquiry)
class CustomerInquiryAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'created_at', 'is_processed')
    list_filter = ('is_processed', 'created_at')
    search_fields = ('phone_number', 'inquiry_text')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('role', 'user', 'created_at', 'session_id')
    list_filter = ('role', 'created_at')
    search_fields = ('content', 'user__email', 'session_id')
