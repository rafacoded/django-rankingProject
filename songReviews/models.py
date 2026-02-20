from django.db.models import JSONField
from django.utils import timezone

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django_mongodb_backend.fields import ArrayField
from django_mongodb_backend.models import EmbeddedModel
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, UserManager


# Create your models here.

# python manage.py make migrations -> prepara sql script
# python manage.py migrate -> script --> BD

#SQLITE MODELS
class UserManager(BaseUserManager):

    def create_user(self, username, mail, role="client", password = None):
        if not mail:
            raise ValueError("Users must have an email address")
        if not username:
            raise ValueError("Users must have a username")

        mail = self.normalize_email(mail)
        user = self.model(username = username, mail=mail , role=role)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, mail, role='admin', password = None):
        user = self.create_user(username, mail, role, password)
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)
        return user

class User(AbstractBaseUser, PermissionsMixin):

    ROLES = (
        ('admin', 'Administrator'),
        ('client', 'Client')
    )
    mail = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    role = models.CharField(max_length=10, choices=ROLES, default="client")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['mail']

    def __str__(self):
        return self.username

    class Meta:
        db_table = 'users'
        managed = True


class Song(models.Model):
    code = models.IntegerField( null=False, unique=True)
    name = models.CharField(max_length=100, null=False)
    artist = models.CharField(max_length=100, null=False) #Nombre
    duration = models.IntegerField(null=False) #Minutos i guess
    artwork = models.URLField() #Art Cover
    releaseDate = models.CharField(max_length=10, null=False)
    categories = ArrayField(models.IntegerField(), blank=True, default=list)

    class Meta:
        db_table = 'songs'
        managed = False

    def __str__(self):
        return self.name or f"Song #{self.code}"

class Category(models.Model):
    code = models.IntegerField(null=False, unique=True)
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(max_length=300, null=False)
    logo = models.URLField()

    class Meta:
        db_table = 'categories'
        managed = False

    def __str__(self):
        return self.name

class Review(models.Model):
    user = models.CharField(max_length=150)
    songCode = models.IntegerField(null=False)
    reviewDate = models.DateTimeField(default=timezone.now)
    rating = models.PositiveIntegerField(null=False, validators=[MinValueValidator(1), MaxValueValidator(5)])
    comments = models.TextField(max_length=300)

    class Meta:
        db_table = 'reviews'
        managed = False

    def __str__(self):
        return self.user + ' ' + str(self.rating)


class Ranking(models.Model):
    user = models.CharField(max_length=150)
    rankingDate = models.DateTimeField(default=timezone.now)
    categoryCode = models.IntegerField(null=False)
    rankList = JSONField(default=list)

    def __str__(self):
        return self.user + ' ' + str(self.categoryCode)

    class Meta:
        db_table = 'ranking'
        managed = False

