from django import forms
from .models import User, Season, GameType, Participation, GameRules, Round


class ProfileCompletionForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'gender', 'primary_phone', 'secondary_phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'primary_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Primary Phone'}),
            'secondary_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Secondary Phone'}),
        }


class SeasonForm(forms.ModelForm):
    class Meta:
        model = Season
        fields = ['name', 'start_date', 'end_date', 'is_active', 'register_start_date', 'register_end_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Spring 2026'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'register_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'register_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class GameTypeForm(forms.ModelForm):
    class Meta:
        model = GameType
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Singles'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Describe this game type...', 'rows': 4}),
        }


class ParticipationForm(forms.ModelForm):
    class Meta:
        model = Participation
        fields = ['season', 'game_type', 'name', 'charge', 'enrolled_users', 'enrolled_teams']
        widgets = {
            'season': forms.Select(attrs={'class': 'form-control'}),
            'game_type': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.Select(attrs={'class': 'form-control'}),
            'charge': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'enrolled_users': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'enrolled_teams': forms.SelectMultiple(attrs={'class': 'form-control'}),
        }


class GameRulesForm(forms.ModelForm):
    class Meta:
        model = GameRules
        fields = ['game_type', 'rules', 'order']
        widgets = {
            'game_type': forms.Select(attrs={'class': 'form-control'}),
            'rules': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter rule text...', 'rows': 4}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        }


class RoundCreateForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Semifinals'}),
    )
    order = forms.IntegerField(
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 5'}),
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned:
            return cleaned
        s, e = cleaned.get('start_date'), cleaned.get('end_date')
        if s and e and e < s:
            raise forms.ValidationError('End date must be on or after start date.')
        return cleaned


class PromoteWinnersForm(forms.Form):
    from_round = forms.ModelChoiceField(
        label='Take winners from',
        queryset=Round.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    def __init__(self, participation, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = participation.rounds.all().order_by('start_date', 'id')
        self.fields['from_round'].queryset = qs
        if qs.exists():
            self.fields['from_round'].empty_label = None


from .models import Team

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'category', 'is_recruiting']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Strike Force'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'is_recruiting': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class AddMemberForm(forms.Form):
    identifier = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Email or Phone Number'}),
        help_text="Enter the registered email or primary phone of the user."
    )
