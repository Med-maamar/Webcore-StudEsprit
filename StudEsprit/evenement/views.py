from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from .models import Event, EventRegistration
from django.urls import reverse
from django import forms
import json
import os
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime
from django.template.loader import render_to_string
from django.http import HttpResponse

# =======================
# API pour idées d'événements
# =======================
@csrf_exempt
def get_event_ideas(request):
    if request.method == "GET":
        period = request.GET.get('period', '')
        try:
            json_path = os.path.join(settings.BASE_DIR, 'dashboard', 'Data', 'event_ideas.json')
            if not os.path.exists(json_path):
                return JsonResponse({"error": "Fichier dataset non trouvé. Vérifiez le chemin ou le fichier."}, status=500)
            with open(json_path, 'r', encoding='utf-8') as file:
                ideas = json.load(file)
            filtered_ideas = [idea for idea in ideas if f"{idea['periode_debut']}-{idea['periode_fin']}" == period]
            if not filtered_ideas:
                return JsonResponse({"error": "Aucune idée disponible pour cette période."}, status=404)
            return JsonResponse({"ideas": filtered_ideas})
        except FileNotFoundError:
            return JsonResponse({"error": "Fichier dataset non trouvé."}, status=500)
        except json.JSONDecodeError as e:
            return JsonResponse({"error": f"Erreur JSON : {str(e)}"}, status=500)
        except Exception as e:
            return JsonResponse({"error": f"Erreur interne : {str(e)}"}, status=500)
    return JsonResponse({"error": "Méthode GET uniquement"}, status=405)


# =======================
# API pour adresses selon type d'événement
# =======================
@csrf_exempt
def get_event_locations(request):
    if request.method == "GET":
        event_type = request.GET.get('type_evenement', '').strip()
        if not event_type:
            return JsonResponse({"error": "Veuillez spécifier un type d'événement."}, status=400)
        
        try:
            json_path = os.path.join(settings.BASE_DIR, 'dashboard', 'Data', 'event_locations.json')
            if not os.path.exists(json_path):
                return JsonResponse({"error": "Fichier dataset des adresses non trouvé."}, status=500)
            
            with open(json_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            matching_addresses = []
            for item in data:
                if event_type.lower() in item.get("type_evenement", "").lower():
                    matching_addresses.extend(item.get("adresses", []))
            
            if not matching_addresses:
                return JsonResponse({"error": f"Aucune adresse trouvée pour '{event_type}'."}, status=404)
            
            return JsonResponse({"adresses": matching_addresses})
        
        except json.JSONDecodeError as e:
            return JsonResponse({"error": f"Erreur JSON invalide : {str(e)}"}, status=500)
        except Exception as e:
            return JsonResponse({"error": f"Erreur interne : {str(e)}"}, status=500)
    
    return JsonResponse({"error": "Méthode GET uniquement"}, status=405)


# =======================
# Liste des événements (admin)
# =======================
def event_list(request):
    events = Event.objects.all().order_by('-start_datetime')
    now = timezone.now()
    upcoming_event = Event.objects.filter(start_datetime__gte=now).order_by('start_datetime').first()
    return render(request, 'evenement/event_list.html', {
        'events': events,
        'upcoming_event': upcoming_event
    })


# =======================
# Liste des événements publics
# =======================
def public_event_list(request):
    events = Event.objects.filter(is_public=True).order_by('-start_datetime')
    now = timezone.now()
    upcoming_event = Event.objects.filter(is_public=True, start_datetime__gte=now).order_by('start_datetime').first()
    return render(request, 'evenement/public_event_list.html', {
        'events': events,
        'upcoming_event': upcoming_event
    })


# =======================
# Détail d'un événement (public + admin)
# =======================
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    # Public users can see only public events
    if not event.is_public and not request.user.is_authenticated:
        messages.error(request, "Cet événement n’est pas public.")
        return redirect('evenement:public_event_list')
    
    # Check if user is already registered (for the button)
    user_is_registered = False
    if request.user.is_authenticated:
        user_is_registered = EventRegistration.objects.filter(event=event, student=request.user).exists()

    return render(request, 'evenement/event_detail.html', {
        'event': event,
        'user_is_registered': user_is_registered
    })


# =======================
# Inscription à un événement
# =======================
def event_register(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not event.is_public:
        messages.error(request, "Inscription impossible : événement non public.")
        return redirect('evenement:public_event_list')
    
    if not request.user.is_authenticated:
        messages.warning(request, "Vous devez être connecté pour vous inscrire.")
        return redirect('account:login')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '')
        email = request.POST.get('email', '')
        motivation = request.POST.get('motivation', '')
        additional_info = request.POST.get('additional_info', '')

        if EventRegistration.objects.filter(event=event, student=request.user).exists():
            messages.warning(request, "Vous êtes déjà inscrit à cet événement.")
            return redirect('evenement:event_detail', event_id=event.id)

        EventRegistration.objects.create(
            event=event,
            student=request.user,
            full_name=full_name,
            email=email,
            motivation=motivation,
            additional_info=additional_info
        )
        messages.success(request, "Votre inscription a été soumise avec succès.")
        return redirect('evenement:event_detail', event_id=event.id)
    
    return render(request, 'evenement/event_register.html', {'event': event})


# =======================
# Validation admin des inscriptions
# =======================
@user_passes_test(lambda u: u.is_superuser)
def registrations_admin(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    registrations = EventRegistration.objects.filter(event=event)
    if request.method == 'POST':
        reg_id = request.POST.get('reg_id')
        action = request.POST.get('action')
        reg = get_object_or_404(EventRegistration, id=reg_id, event=event)
        if action == 'approve':
            reg.is_approved = True
            reg.save()
            messages.success(request, "Inscription approuvée.")
        elif action == 'reject':
            reg.is_approved = False
            reg.save()
            messages.info(request, "Inscription refusée.")
        return redirect('evenement:registrations_admin', event_id=event.id)
    return render(request, 'evenement/registrations_admin.html', {'event': event, 'registrations': registrations})


# =======================
# Formulaire Event
# =======================
class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'start_datetime', 'end_datetime', 'location', 'is_public'
        ]
        widgets = {
            'start_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


# =======================
# Création d'événement
# =======================
@user_passes_test(lambda u: hasattr(u, 'role') and u.role.lower() in ["admin", "superuser"])
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Événement créé avec succès.")
            return redirect('evenement:event_list')
    else:
        initial_data = {
            'title': request.GET.get('title', ''),
            'description': request.GET.get('description', ''),
            'location': request.GET.get('location', ''),
            'is_public': False,
        }
        form = EventForm(initial=initial_data)
    return render(request, 'evenement/event_create.html', {'form': form})


# =======================
# Edition d'événement
# =======================
@user_passes_test(lambda u: hasattr(u, 'role') and u.role.lower() in ["admin", "superuser"])
def event_edit(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    field = request.GET.get('field')
    if not field or field not in {'title', 'description', 'start_datetime', 'end_datetime', 'location', 'is_public'}:
        return render(request, 'evenement/event_edit_select.html', {'event': event})

    class SingleFieldForm(forms.ModelForm):
        class Meta:
            model = Event
            fields = [field]
            widgets = {
                'start_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
                'end_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            }

    if request.method == 'POST':
        form = SingleFieldForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, f"{field} mis à jour avec succès.")
            return redirect('evenement:event_list')
    else:
        form = SingleFieldForm(instance=event)

    return render(request, 'evenement/event_edit.html', {'form': form, 'field': field, 'event': event})



def search_events(request):
    query = request.GET.get('q', '').strip()
    events = Event.objects.filter(is_public=True)
    if query:
        events = events.filter(title__icontains=query)  # recherche par titre
    
    events = events.order_by('-start_datetime')

    # On génère le HTML partiel
    html = render_to_string('evenement/_event_list_partial.html', {'events': events})
    return HttpResponse(html)

# =======================
# Suppression d'événement
# =======================
@user_passes_test(lambda u: hasattr(u, 'role') and u.role.lower() in ["admin", "superuser"])
def event_delete(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        event.delete()
        messages.success(request, "Événement supprimé avec succès.")
        return redirect('evenement:event_list')
    return render(request, 'evenement/event_confirm_delete.html', {'event': event})