import django_filters.rest_framework
import codecs
from django.http import HttpResponse
from django.conf import settings
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response

from .models import Voting, CandidatesGroup, Candidate
from .serializers import SimpleVotingSerializer, VotingSerializer
from base.perms import UserIsStaff
from base.models import Auth
from django.http import HttpResponseRedirect
from django.shortcuts import render

from .forms import UploadFileForm, NewVotingForm
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import requires_csrf_token
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from rest_framework.renderers import JSONRenderer
from django.contrib.auth.decorators import user_passes_test

import json
import csv
import os
import markdown

dirspot = os.getcwd()

@user_passes_test(lambda user: user.is_superuser, login_url="/")
def candidates_load(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            validation_errors = handle_uploaded_file(request.FILES['file'])
            if len(validation_errors) > 0:
                return render(request, dirspot+'/voting/templates/upload.html', {'form': form, 'validation_errors': validation_errors})
            else:
                return HttpResponseRedirect('/admin/')
    else:
        form = UploadFileForm()
    return render(request, dirspot+'/voting/templates/upload.html', {'form': form})

@user_passes_test(lambda user: user.is_superuser, login_url="/")
def voting_edit(request):

    auths = Auth.objects.all()

    if request.method == 'POST':
        form = NewVotingForm(request.POST, request.FILES)

        votingName = request.POST["name"]
        votingDescription = request.POST["description"]
        start_date_selected = request.POST["start_date_selected"]
        end_date_selected = request.POST["end_date_selected"]
        custom_url = request.POST["custom_url"]
        if start_date_selected == "":
            start_date_selected = None
        if end_date_selected == "":
            end_date_selected = None
        
        permission_classes = (UserIsStaff,)
        #for data in ['name', 'desc', 'candidatures']:
        #    if not data in request.data:
        #        return Response({}, status=status.HTTP_400_BAD_REQUEST)

        if form.is_valid:
            candidatures = request.POST.getlist("candidatures")
            voting = Voting(name=votingName, desc=votingDescription, custom_url=custom_url, start_date_selected=start_date_selected, end_date_selected=end_date_selected)
                    #candidatures=request.data.get('candidatures'))
                    #question=question)
            
            if custom_url is None:
                voting.save()
            else:
                try:
                    encuentraVotacionConCustomURL = Voting.objects.get(custom_url=custom_url)
                    return render(request, dirspot+'/voting/templates/newVotingForm.html', {'form': form, 'auths':auths, 'mensaje':'Esta url ya existe, elija otra', 'voting':voting})
                except Exception:    
                    voting.save()

            candidatures_db = []
            for candidature in candidatures:
                try:
                    c = CandidatesGroup.objects.get(name=candidature)
                    candidatures_db.append(c)
                except:
                    CandidatesGroup(name=candidature).save()
                    c = CandidatesGroup.objects.get(name=candidature)
                    candidatures_db.append(c)
            
            for cand in candidatures_db:
                voting.candidatures.add(cand)

            auths = request.POST.getlist("auths")
            auths_db = Auth.objects.all()
            auths_selected = []

            for at in auths_db:
                for ah in auths:
                    if at.name == ah:
                        auths_selected.append(at)

            for a in auths_selected:
                voting.auths.add(a)
            #Accion que se debe realizar en la lista
            #voting.create_pubkey()
        votings = Voting.objects.all()
        return render(request, 'votings.html', {'votings': votings})    
    else:
        form = NewVotingForm()
    return render(request, dirspot+'/voting/templates/newVotingForm.html', {'form': form, 'auths':auths})

@transaction.atomic
@csrf_exempt
def handle_uploaded_file(response):
    rows = response.POST['param'].split("\n")

    validation_errors = []
    provincias = ['VI', 'AB', 'A', 'AL', 'AV', 'BA', 'PM', 'B', 'BU', 'CC', 'CA', 'CS', 'CR', 'CO', 'C', 'CU', 'GI', 'GR', 'GU', 'SS', 'H', 'HU', 'J', 'LE', 
        'L', 'LO', 'LU', 'M', 'MA', 'MU', 'NA', 'OR', 'O', 'P', 'GC', 'PO', 'SA', 'TF', 'S', 'SG', 'SE', 'SO', 'T', 'TE', 'TO', 'V', 'VA', 'BI', 'ZA', 'Z', 'CE', 'ML']
    count_provincias = dict((prov, 0) for prov in provincias)
    row_line = 1
    maleCount = 0
    femaleCount = 0
    count_presidents = 0
    candidature_name = response.POST['candidature_name']

    for row in rows:
        if row_line != 1:
            user = row.split("#")

            if len(user) > 1 :
                name = user[0]
                _type = user[1]
                born_area = user[2]
                current_area = user[3]
                primaries = user[4]
                sex = user[5]
                candidatesGroupName = response.POST['candidature_name']

                if sex == "HOMBRE":
                    maleCount = maleCount + 1
                else:
                    femaleCount = femaleCount + 1

                if primaries == 'FALSE':
                    primaries = False
                    validation_errors.append("Error en la línea " + str(row_line) + ": El candidato " + str(name) + " no ha pasado el proceso de primarias")
                else:
                    primaries = True

                if _type == "PRESIDENCIA":
                    count_presidents = count_presidents + 1

                if _type == 'CANDIDATO' and (born_area in count_provincias and current_area in count_provincias):
                    if born_area == current_area:
                        count_provincias[born_area] = count_provincias[born_area] + 1

                    else:
                        count_provincias[current_area] = count_provincias[current_area] + 1
                        count_provincias[born_area] = count_provincias[born_area] + 1


                try:
                    CandidatesGroup.objects.get(name=candidatesGroupName)
                except:
                    CandidatesGroup(name=candidatesGroupName).save()

                try:
                    candidato = Candidate(name=name, type=_type, born_area=born_area, current_area=current_area, primaries= primaries, sex=sex, candidatesGroup=CandidatesGroup.objects.get(name=candidatesGroupName))
                    candidato.full_clean()
                except ValidationError:
                    validation_errors.append("Error en la línea " + str(row_line) + ": Hay errores de formato/validación")
                else:
                    candidato.save()
            
        row_line = row_line + 1

    if count_presidents > 1:
            validation_errors.append("La candidatura " + candidatesGroupName + " tiene más de un candidato a presidente")

    malePercentage = (maleCount*100)/(maleCount+femaleCount)
    if  malePercentage > 60 or malePercentage < 40:
        validation_errors.append("La candidatura " + candidatesGroupName + " no cumple un balance 60-40 entre hombres y mujeres")
    if maleCount + femaleCount > 350:
        validation_errors.append("La candidatura " + candidatesGroupName + " supera el máximo de candidatos permitidos (350)")
    
    provincias_validacion = [prov for prov in provincias if count_provincias[prov] < 2]

    for prov in provincias_validacion:
        validation_errors.append("Tiene que haber al menos dos candidatos al congreso cuya provincia de nacimiento o de residencia tenga de código " + prov) 


    if len(validation_errors) > 0:
        transaction.set_rollback(True)

    html = ""
    if len(validation_errors) > 0:
        html = '<div id="errors'
        html = html + str(candidature_name)
        html = html +'" style="color: #D63301;background-color: #FFCCBA;border-radius: 1em;padding: 1em;border-style: solid;border-width: 1px;border-color: #D63301;">'
        html = html + '<p style="text-align: left; width: 100%; size: 24px !important; font-weight: bold !important;"> La candidatura ' + candidatesGroupName + ' tiene los siguientes errores: </p><ul>'
        for error in validation_errors:
            html = html + '<li style="text-align: left; padding-left: 15px;"> ' + error + '</li>'
        html = html + '<ul/></div>'
    return HttpResponse(html)

@user_passes_test(lambda user: user.is_superuser, login_url="/")
def voting_list(request):
    votings = Voting.objects.all()
    return render(request, "votings.html", {'votings':votings, 'errors': False, 'STATIC_URL':settings.STATIC_URL})


@user_passes_test(lambda user: user.is_superuser, login_url="/")
def voting_list_update(request):
    voting_id = request.POST['voting_id']
    voting = get_object_or_404(Voting, pk=voting_id)
    action = request.POST['action']
    error = False
    msg = ""
    if action == 'start':
        if voting.start_date:
            msg = "Error: La votación ya ha comenzado"
            error = True
        else:
            voting.start_date = timezone.now()
            voting.save()
    elif action == 'stop':
        if not voting.start_date:
            msg = "Error: La votación ya ha comenzado"
            error = True
        elif voting.end_date:
            msg = "Error: La votación ya ha finalizado"
            error = True
        else:
            voting.end_date = timezone.now()
            voting.save()
    elif action == 'tally':
        if not voting.start_date:
            msg = "Error: La votación no ha comenzado"
            error = True
        elif not voting.end_date:
            msg = "Error: La votación no ha finalizado"
            error = True
        elif voting.tally:
            msg = "Error: La votación ya ha sido contada"
            error = True
        else:
            voting.tally_votes(request.auth.key)
    elif action == 'delete':
        voting.delete()
    else:
        msg = "Error"
        error = True

    votings = Voting.objects.all()
    return render(request, "votings.html", {'votings':votings, 'errors':error, 'msg':msg})

@user_passes_test(lambda user: user.is_superuser, login_url="/")
def voting_list_update_multiple(request):
    array_voting_id = request.POST['array_voting_id[]'].split(",")
    action = request.POST['action_multiple']
    for voting_id in array_voting_id:
        voting = get_object_or_404(Voting, pk=voting_id)
        error = False
        msg = ""
        if action == 'start':
            if voting.start_date:
                msg = "Error: La votación ya ha comenzado"
                error = True
                break
            else:
                voting.start_date = timezone.now()
                voting.save()
        elif action == 'stop':
            if not voting.start_date:
                msg = "Error: La votación ya ha comenzado"
                error = True
                break
            elif voting.end_date:
                msg = "Error: La votación ya ha finalizado"
                error = True
                break
            else:
                voting.end_date = timezone.now()
                voting.save()
        elif action == 'tally':
            if not voting.start_date:
                msg = "Error: La votación no ha comenzado"
                error = True
                break
            elif not voting.end_date:
                msg = "Error: La votación no ha finalizado"
                error = True
                break
            elif voting.tally:
                msg = "Error: La votación ya ha sido contada"
                error = True
                break
            else:
                voting.tally_votes(request.auth.key)
        elif action == 'delete':
                voting.delete()
        else:
            msg = "Error"
            error = True
            break

    votings = Voting.objects.all()
    return render(request, "votings.html", {'votings':votings, 'errors':error, 'msg':msg})
    
class VotingView(generics.ListCreateAPIView):
    queryset = Voting.objects.all()
    serializer_class = VotingSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filter_fields = ('id', )

    def get(self, request, *args, **kwargs):
        version = request.version
        if version not in settings.ALLOWED_VERSIONS:
            version = settings.DEFAULT_VERSION
        if version == 'v2':
            self.serializer_class = VotingSerializer

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.permission_classes = (UserIsStaff,)
        self.check_permissions(request)
        for data in ['name', 'desc', 'candidatures']:
            if not data in request.data:
                return Response({}, status=status.HTTP_400_BAD_REQUEST)

        #question = Question(desc=request.data.get('question'))
        #question.save()
        #for idx, q_opt in enumerate(request.data.get('question_opt')):
        #    opt = QuestionOption(question=question, option=q_opt, number=idx)
        #    opt.save()
        voting = Voting(name=request.data.get('name'), desc=request.data.get('desc'),
                candidates=request.data.get('candidatures'))
                #question=question)
        voting.save()

        auth, _ = Auth.objects.get_or_create(url=settings.BASEURL,
                                          defaults={'me': True, 'name': 'test auth'})
        auth.save()
        voting.auths.add(auth)

        return Response({}, status=status.HTTP_201_CREATED)


class VotingUpdate(generics.RetrieveUpdateDestroyAPIView):
    queryset = Voting.objects.all()
    serializer_class = VotingSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    permission_classes = (UserIsStaff,)

    def put(self, request, voting_id, *args, **kwars):
        action = request.data.get('action')
        if not action:
            return Response({}, status=status.HTTP_400_BAD_REQUEST)

        voting = get_object_or_404(Voting, pk=voting_id)
        msg = ''
        st = status.HTTP_200_OK
        if action == 'start':
            if voting.start_date:
                msg = 'Voting already started'
                st = status.HTTP_400_BAD_REQUEST
            else:
                voting.start_date = timezone.now()
                voting.save()
                msg = 'Voting started'
        elif action == 'stop':
            if not voting.start_date:
                msg = 'Voting is not started'
                st = status.HTTP_400_BAD_REQUEST
            elif voting.end_date:
                msg = 'Voting already stopped'
                st = status.HTTP_400_BAD_REQUEST
            else:
                voting.end_date = timezone.now()
                voting.save()
                msg = 'Voting stopped'
        elif action == 'tally':
            if not voting.start_date:
                msg = 'Voting is not started'
                st = status.HTTP_400_BAD_REQUEST
            elif not voting.end_date:
                msg = 'Voting is not stopped'
                st = status.HTTP_400_BAD_REQUEST
            elif voting.tally:
                msg = 'Voting already tallied'
                st = status.HTTP_400_BAD_REQUEST
            else:
                voting.tally_votes(request.auth.key)
                msg = 'Voting tallied'
        else:
            msg = 'Action not found, try with start, stop or tally'
            st = status.HTTP_400_BAD_REQUEST
        return Response(msg, status=st)

@user_passes_test(lambda user: user.is_superuser, login_url="/")
def getVoting(request):
    id_voting = request.GET['id']
    voting = get_object_or_404(Voting, pk=id_voting)

    voting_json = VotingSerializer(voting)
    data = JSONRenderer().render(voting_json.data)
    return HttpResponse(data)

@user_passes_test(lambda user: user.is_superuser, login_url="/")
@csrf_exempt
def create_auth(request):
    name = request.POST["auth_name"]
    baseurl = request.POST["base_url"]
    auth_me = request.POST["auth_me"]

    if auth_me == 'True':
        me = True
    elif auth_me == 'False':
        me = False


    Auth.objects.get_or_create(url=baseurl, defaults={'me': me, 'name': name})

    auths = Auth.objects.all()

    if Auth.objects.get(url=baseurl):
        st = status.HTTP_200_OK
    else:
        st = status.HTTP_500_INTERNAL_SERVER_ERROR

    return HttpResponse({'auths':auths}, status=st)

def copy_voting(request, voting_id):
    voting = get_object_or_404(Voting, pk=voting_id)
    votingName = voting.name
    votingDescription = voting.desc
    candidatures = voting.candidatures.all()
    auths = voting.auths.all()
    new_voting = Voting(name=votingName, desc=votingDescription)
    new_voting.save()
    new_voting.candidatures.set(candidatures)
    new_voting.auths.set(auths)

    new_voting.save()
    return HttpResponseRedirect("/voting/votings")

def show_voting(request, voting):

    if type(voting) is int:
        votacion = get_object_or_404(Voting, pk=voting)
    elif type(voting) is str:
        votacion = get_object_or_404(Voting, custom_url=voting)

    candidates = {}
    for candidature in votacion.candidatures.all():
        candidates_candidature = Candidate.objects.all().filter(candidatesGroup=candidature)
        candidates[candidature.id] = candidates_candidature

    return render(request, 'showVoting.html', {'voting': votacion, 'candidates' : candidates, 'description_markdown': markdown.markdown(votacion.desc)})