from django.db import models
from django.contrib.postgres.fields import JSONField
from django.db.models.signals import post_save
from django.dispatch import receiver

from base import mods
from base.models import Auth, Key

class CandidatesGroup(models.Model):
    name = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name

class Candidate(models.Model):
    PROVINCIAS = (('VI', 'Álava'),        
        ('AB', 'Albacete'),     
        ('A', 'Alacant'),       
        ('AL', 'Almería'),      
        ('AV', 'Ávila'),        
        ('BA', 'Badajoz'),      
        ('PM', 'Illes Balears'),
        ('B', 'Barcelona'),     
        ('BU', 'Burgos'),       
        ('CC', 'Cáceres'),
        ('CA', 'Cádiz'),
        ('CS', 'Castelló'),
        ('CR', 'Ciudad Real'),
        ('CO', 'Córdoba'),
        ('C', 'A Coruña'),
        ('CU', 'Cuenca'),
        ('GI', 'Girona'),
        ('GR', 'Granada'),
        ('GU', 'Guadalajara'),
        ('SS', 'Gipuzkoa'),
        ('H', 'Huelva'),
        ('HU', 'Huesca'),
        ('J', 'Jaén'),
        ('LE', 'León'),
        ('L', 'Lleida'),
        ('LO', 'La Rioja'),
        ('LU', 'Lugo'),
        ('M', 'Madrid'),
        ('MA', 'Málaga'),
        ('MU', 'Murcia'),
        ('NA', 'Nafarroa'),
        ('OR', 'Ourense'),
        ('O', 'Asturias'),
        ('P', 'Palencia'),
        ('GC', 'Las Palmas'),
        ('PO', 'Pontevedra'),
        ('SA', 'Salamanca'),
        ('TF', 'Sta. Cruz de Tenerife'),
        ('S', 'Cantabria'),
        ('SG', 'Segovia'),
        ('SE', 'Sevilla'),
        ('SO', 'Soria'),
        ('T', 'Tarragona'),
        ('TE', 'Teruel'),
        ('TO', 'Toledo'),
        ('V', 'Valéncia'),
        ('VA', 'Valladolid'),
        ('BI', 'Bizkaia'),
        ('ZA', 'Zamora'),
        ('Z', 'Zaragoza'),
        ('CE', 'Ceuta'),
        ('ML', 'Melilla'))

    name = models.TextField(default="CANDIDATO")
    type = models.TextField(default="CANDIDATO", choices=[('PRESIDENCIA', 'PRESIDENCIA'),('CANDIDATO', 'CANDIDATO'),])
    born_area = models.TextField(choices=PROVINCIAS, default='AB')
    current_area = models.TextField(choices=PROVINCIAS, default='AB')
    primaries = models.BooleanField(default=False)
    sex = models.TextField(choices=[('HOMBRE', 'HOMBRE'),('MUJER', 'MUJER'),], default="HOMBRE")
    candidatesGroup = models.ForeignKey(CandidatesGroup, on_delete=models.CASCADE)

class Question(models.Model):
    desc = models.TextField()

    def __str__(self):
        return self.desc


class QuestionOption(models.Model):
    question = models.ForeignKey(Question, related_name='options', on_delete=models.CASCADE)
    number = models.PositiveIntegerField(blank=True, null=True)
    option = models.TextField()

    def save(self):
        if not self.number:
            self.number = self.question.options.count() + 2
        return super().save()

    def __str__(self):
        return '{} ({})'.format(self.option, self.number)


class Voting(models.Model):
    
    name = models.CharField(max_length=200)
    desc = models.TextField(blank=True, null=True)
    question = models.ForeignKey(Question, related_name='voting', on_delete=models.CASCADE)

    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)

    start_date_selected = models.DateTimeField(blank=False, null=True)
    end_date_selected = models.DateTimeField(blank=True, null=True)

    pub_key = models.OneToOneField(Key, related_name='voting', blank=True, null=True, on_delete=models.SET_NULL)
    auths = models.ManyToManyField(Auth, related_name='votings')

    tally = JSONField(blank=True, null=True)
    postproc = JSONField(blank=True, null=True)

    custom_url = models.CharField(max_length=200, blank=True, null=True, unique=True)

    def create_pubkey(self):
        if self.pub_key or not self.auths.count():
            return

        auth = self.auths.first()
        data = {
            "voting": self.id,
            "auths": [ {"name": a.name, "url": a.url} for a in self.auths.all() ],
        }
        key = mods.post('mixnet', baseurl=auth.url, json=data)
        pk = Key(p=key["p"], g=key["g"], y=key["y"])
        pk.save()
        self.pub_key = pk
        self.save()

    def get_votes(self, token=''):
        # gettings votes from store
        votes = mods.get('store', params={'voting_id': self.id}, HTTP_AUTHORIZATION='Token ' + token)
        # anon votes
        return [[i['a'], i['b']] for i in votes]

    def tally_votes(self, token=''):
        '''
        The tally is a shuffle and then a decrypt
        '''

        votes = self.get_votes(token)

        auth = self.auths.first()
        shuffle_url = "/shuffle/{}/".format(self.id)
        decrypt_url = "/decrypt/{}/".format(self.id)
        auths = [{"name": a.name, "url": a.url} for a in self.auths.all()]

        # first, we do the shuffle
        data = { "msgs": votes }
        response = mods.post('mixnet', entry_point=shuffle_url, baseurl=auth.url, json=data,
                response=True)
        if response.status_code != 200:
            # TODO: manage error
            pass

        # then, we can decrypt that
        data = {"msgs": response.json()}
        response = mods.post('mixnet', entry_point=decrypt_url, baseurl=auth.url, json=data,
                response=True)

        if response.status_code != 200:
            # TODO: manage error
            pass

        self.tally = response.json()
        self.save()

        self.do_postproc()

    def do_postproc(self):
        tally = self.tally
        options = self.question.options.all()

        opts = []
        for opt in options:
            if isinstance(tally, list):
                votes = tally.count(opt.number)
            else:
                votes = 0
            opts.append({
                'option': opt.option,
                'number': opt.number,
                'votes': votes
            })

        data = { 'type': 'IDENTITY', 'options': opts }
        postp = mods.post('postproc', json=data)

        self.postproc = postp
        self.save()

    def __str__(self):
        return self.name
