from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Event, EventRegistration
from django.urls import reverse
from django import forms

# Liste des événements
def event_list(request):
    events = Event.objects.all().order_by('-start_datetime')
    return render(request, 'evenement/event_list.html', {'events': events})

# Détail d'un événement
@login_required
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, 'evenement/event_detail.html', {'event': event})

# Inscription à un événement (formulaire)
@login_required
def event_register(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '')
        email = request.POST.get('email', '')
        motivation = request.POST.get('motivation', '')
        additional_info = request.POST.get('additional_info', '')
        # Vérifier si déjà inscrit
        if EventRegistration.objects.filter(event=event, student=request.user).exists():
            messages.warning(request, "Vous êtes déjà inscrit à cet événement.")
            return redirect(reverse('evenement:event_detail', args=[event.id]))
        EventRegistration.objects.create(
            event=event,
            student=request.user,
            full_name=full_name,
            email=email,
            motivation=motivation,
            additional_info=additional_info
        )
        messages.success(request, "Votre inscription a été soumise avec succès.")
        return redirect(reverse('evenement:event_detail', args=[event.id]))
    return render(request, 'evenement/event_register.html', {'event': event})

# Validation admin des inscriptions
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
        return redirect(reverse('evenement:registrations_admin', args=[event.id]))
    return render(request, 'evenement/registrations_admin.html', {'event': event, 'registrations': registrations})

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

@user_passes_test(lambda u: hasattr(u, 'role') and u.role.lower() in ["admin", "superuser"])
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            # Ne pas affecter organizer si ce n'est pas un User Django natif
            event.save()
            messages.success(request, "Événement créé avec succès.")
            return redirect('evenement:event_list')
    else:
        form = EventForm()
    return render(request, 'evenement/event_create.html', {'form': form})


@user_passes_test(lambda u: hasattr(u, 'role') and u.role.lower() in ["admin", "superuser"]) 
def event_edit(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    # field to edit passed as query param ?field=title or description etc.
    field = request.GET.get('field')
    if not field or field not in {'title', 'description', 'start_datetime', 'end_datetime', 'location', 'is_public'}:
        # show choices of editable fields
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


@user_passes_test(lambda u: hasattr(u, 'role') and u.role.lower() in ["admin", "superuser"])
def event_delete(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        event.delete()
        messages.success(request, "Événement supprimé avec succès.")
        return redirect('evenement:event_list')
    # If GET, show a confirmation page
    return render(request, 'evenement/event_confirm_delete.html', {'event': event})
