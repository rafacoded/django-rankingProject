from django import forms
from django.contrib.auth.forms import AuthenticationForm

from songReviews.models import *

class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))
    repeat_password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))

    class Meta:
        model = User
        fields = ("username", "mail")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "mail": forms.EmailInput(attrs={"class": "form-control"}),
        }

    # Placeholders
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].widget.attrs.update({"placeholder": "Your username"})
        self.fields["mail"].widget.attrs.update({"placeholder": "you@example.com"})
        self.fields["password"].widget.attrs.update({"placeholder": "Password"})
        self.fields["repeat_password"].widget.attrs.update({"placeholder": "Repeat password"})

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Username"})
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Password"})
    )