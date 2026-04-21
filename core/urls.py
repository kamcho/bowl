from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('complete-profile/', views.complete_profile, name='complete_profile'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # Season
    path('manage/seasons/', views.season_list, name='season_list'),
    path('manage/seasons/create/', views.season_create, name='season_create'),
    path('manage/seasons/<int:pk>/', views.season_detail, name='season_detail'),
    path('manage/seasons/<int:pk>/edit/', views.season_edit, name='season_edit'),
    path('manage/seasons/<int:pk>/delete/', views.season_delete, name='season_delete'),

    # Game Types
    path('manage/game-types/', views.gametype_list, name='gametype_list'),
    path('manage/game-types/create/', views.gametype_create, name='gametype_create'),
    path('manage/game-types/<int:pk>/edit/', views.gametype_edit, name='gametype_edit'),
    path('manage/game-types/<int:pk>/delete/', views.gametype_delete, name='gametype_delete'),

    # Participations
    path('manage/participations/', views.participation_list, name='participation_list'),
    path('manage/participations/create/', views.participation_create, name='participation_create'),
    path('manage/participations/<int:pk>/edit/', views.participation_edit, name='participation_edit'),
    path(
        'manage/participations/<int:pk>/rounds/<int:round_id>/panel/',
        views.participation_round_panel,
        name='participation_round_panel',
    ),
    path(
        'manage/participations/<int:pk>/rounds/<int:round_id>/leaderboard/',
        views.participation_round_leaderboard,
        name='participation_round_leaderboard',
    ),
    path(
        'manage/participations/<int:pk>/challenges/singles/<int:challenge_id>/schedule/',
        views.participation_challenge_schedule,
        {'challenge_type': 'singles'},
        name='participation_singles_challenge_schedule',
    ),
    path(
        'manage/participations/<int:pk>/challenges/team/<int:challenge_id>/schedule/',
        views.participation_challenge_schedule,
        {'challenge_type': 'team'},
        name='participation_team_challenge_schedule',
    ),
    path(
        'manage/participations/<int:pk>/matches/singles/<int:challenge_id>/score/',
        views.match_score_singles,
        name='match_score_singles',
    ),
    path(
        'manage/participations/<int:pk>/matches/team/<int:challenge_id>/score/',
        views.match_score_team,
        name='match_score_team',
    ),
    path('manage/participations/<int:pk>/rounds/create/', views.participation_round_create, name='participation_round_create'),
    path('manage/participations/<int:pk>/rounds/promote/', views.participation_promote_winners, name='participation_promote_winners'),
    path('manage/participations/<int:pk>/delete/', views.participation_delete, name='participation_delete'),
    path('manage/participations/<int:pk>/matches/<int:challenge_id>/quick-score/', views.quick_score_frame, name='quick_score_frame'),

    # Game Rules
    path('manage/rules/', views.gamerules_list, name='gamerules_list'),
    path('manage/rules/create/', views.gamerules_create, name='gamerules_create'),
    path('manage/rules/<int:pk>/edit/', views.gamerules_edit, name='gamerules_edit'),
    path('manage/rules/<int:pk>/delete/', views.gamerules_delete, name='gamerules_delete'),

    # Teams
    path('teams/', views.team_list, name='team_list'),
    path('manage/teams/', views.admin_team_list, name='admin_team_list'),
    path('teams/create/', views.team_create, name='team_create'),
    path('teams/<int:pk>/', views.team_detail, name='team_detail'),
    path('teams/<int:pk>/add-member/', views.team_add_member, name='team_add_member'),
    path('manage/participations/<int:pk>/generate-fixtures/', views.participation_generate_fixtures, name='participation_generate_fixtures'),
    path('manage/participations/<int:pk>/rounds/<int:round_id>/manual-promote/', views.participation_manual_promote, name='participation_manual_promote'),
    path('manage/participations/<int:pk>/rounds/<int:round_id>/complete/', views.participation_round_complete, name='participation_round_complete'),

    # M-Pesa
    path('enroll/<int:pk>/pay/', views.initiate_enrollment_payment, name='initiate_enrollment_payment'),
    path('api/mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('manage/payments/', views.payment_list, name='payment_list'),
    path('chat/', views.chat_assistant, name='chat_assistant'),
    path('manage/chats/', views.chat_logs, name='chat_logs'),
]
