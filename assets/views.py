# assets/views.py
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from .forms import EquipmentForm, SoftwareForm, LicenseForm, InterventionForm
from .models import Equipment, Software, License, Intervention
from .signals import send_intervention_status_update  # Import the status update function
import logging

logger = logging.getLogger(__name__)



class IsAdminMixin(UserPassesTestMixin):
    """Mixin to check if the user is an admin."""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

class IsTechnicianOrAdminMixin(UserPassesTestMixin):
    """Mixin to check if the user is a technician or an admin."""
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_staff or
            getattr(self.request.user, 'role', None) == 'technician'
        )
# --- END OF MODIFIED MIXINS ---

# ----------------------------------
# EQUIPMENT VIEWS
# ----------------------------------

class EquipmentListView(LoginRequiredMixin, ListView):
    model = Equipment
    template_name = 'assets/equipment_list.html'
    context_object_name = 'equipment_list'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('q')
        status_filter = self.request.GET.get('status')
        category_filter = self.request.GET.get('category')
        location_filter = self.request.GET.get('location')

        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(serial_number__icontains=search_query) |
                Q(ip_address__icontains=search_query) |
                Q(mac_address__icontains=search_query)
            )
        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)
        if category_filter:
            queryset = queryset.filter(category__iexact=category_filter)
        if location_filter:
            queryset = queryset.filter(location__icontains=location_filter)

        return queryset.order_by('-purchase_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_search'] = self.request.GET.get('q', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_category'] = self.request.GET.get('category', '')
        context['current_location'] = self.request.GET.get('location', '')
        return context

class EquipmentDetailView(LoginRequiredMixin, DetailView):
    model = Equipment
    template_name = 'assets/equipment_detail.html'
    context_object_name = 'equipment'

# Admin-only views
class EquipmentCreateView(LoginRequiredMixin, IsAdminMixin, CreateView):
    model = Equipment
    form_class = EquipmentForm
    template_name = 'assets/equipment_form.html'
    success_url = reverse_lazy('assets:equipment_list')

class EquipmentUpdateView(LoginRequiredMixin, IsAdminMixin, UpdateView):
    model = Equipment
    form_class = EquipmentForm
    template_name = 'assets/equipment_form.html'
    context_object_name = 'equipment'
    success_url = reverse_lazy('assets:equipment_list')

class EquipmentDeleteView(LoginRequiredMixin, IsAdminMixin, DeleteView):
    model = Equipment
    template_name = 'assets/equipment_confirm_delete.html'
    success_url = reverse_lazy('assets:equipment_list')

# ----------------------------------
# SOFTWARE VIEWS
# ----------------------------------

class SoftwareListView(LoginRequiredMixin, ListView):
    model = Software
    template_name = 'assets/software_list.html'
    context_object_name = 'software_list'
    paginate_by = 20

class SoftwareDetailView(LoginRequiredMixin, DetailView):
    model = Software
    template_name = 'assets/software_details.html'
    context_object_name = 'software'

# Admin-only views
class SoftwareCreateView(LoginRequiredMixin, IsAdminMixin, CreateView):
    model = Software
    form_class = SoftwareForm
    template_name = 'assets/software_form.html'
    success_url = reverse_lazy('assets:software_list')

class SoftwareUpdateView(LoginRequiredMixin, IsAdminMixin, UpdateView):
    model = Software
    form_class = SoftwareForm
    template_name = 'assets/software_form.html'
    context_object_name = 'software'
    success_url = reverse_lazy('assets:software_list')

class SoftwareDeleteView(LoginRequiredMixin, IsAdminMixin, DeleteView):
    model = Software
    template_name = 'assets/software_confirm_delete.html'
    success_url = reverse_lazy('assets:software_list')

# ----------------------------------
# LICENSES VIEWS
# ----------------------------------

class LicenseListView(LoginRequiredMixin, ListView):
    model = License
    template_name = 'assets/licenses_list.html'
    context_object_name = 'license_list'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('q')
        status_filter = self.request.GET.get('status')
        license_type_filter = self.request.GET.get('license_type')

        if search_query:
            queryset = queryset.filter(
                Q(software__name__icontains=search_query) |
                Q(license_key__icontains=search_query) |
                Q(assigned_to__username__icontains=search_query) |
                Q(assigned_to__first_name__icontains=search_query) |
                Q(assigned_to__last_name__icontains=search_query)
            )
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if license_type_filter:
            queryset = queryset.filter(license_type__iexact=license_type_filter)

        return queryset.order_by('software__name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_search'] = self.request.GET.get('q', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_license_type'] = self.request.GET.get('license_type', '')
        return context

class LicenseDetailView(LoginRequiredMixin, DetailView):
    model = License
    template_name = 'assets/licenses_details.html'
    context_object_name = 'license'

# Admin-only views
class LicenseCreateView(LoginRequiredMixin, IsAdminMixin, CreateView):
    model = License
    form_class = LicenseForm
    template_name = 'assets/license_form.html'
    success_url = reverse_lazy('assets:license_list')

class LicenseUpdateView(LoginRequiredMixin, IsAdminMixin, UpdateView):
    model = License
    form_class = LicenseForm
    template_name = 'assets/license_form.html'
    context_object_name = 'license'
    success_url = reverse_lazy('assets:license_list')

class LicenseDeleteView(LoginRequiredMixin, IsAdminMixin, DeleteView):
    model = License
    template_name = 'assets/licenses_confirm_delete.html'
    success_url = reverse_lazy('assets:license_list')

# ----------------------------------
# INTERVENTIONS VIEWS
# ----------------------------------
class InterventionListView(LoginRequiredMixin, ListView):
    model = Intervention
    template_name = 'assets/intervention_list.html'
    context_object_name = 'intervention_list'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('q')
        status_filter = self.request.GET.get('status')
        priority_filter = self.request.GET.get('priority')

        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(equipment__name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)

        return queryset.order_by('-scheduled_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_search'] = self.request.GET.get('q', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_priority'] = self.request.GET.get('priority', '')
        return context


class InterventionDetailView(LoginRequiredMixin, DetailView):
    model = Intervention
    template_name = 'assets/intervention_detail.html'
    context_object_name = 'intervention'


class InterventionCreateView(LoginRequiredMixin, IsTechnicianOrAdminMixin, CreateView):
    model = Intervention
    form_class = InterventionForm
    template_name = 'assets/intervention_form.html'
    success_url = reverse_lazy('assets:intervention_list')

    def form_valid(self, form):
        # Set the technician to the logged-in user
        form.instance.technician = self.request.user

        # Save the intervention (this will trigger the signal automatically)
        response = super().form_valid(form)

        # Add a success message
        messages.success(
            self.request,
            f'Intervention "{self.object.title}" has been created successfully. '
            'Admins have been notified via email.'
        )

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['view'] = {'title': 'Create New Intervention'}
        return context


class InterventionUpdateView(LoginRequiredMixin, IsTechnicianOrAdminMixin, UpdateView):
    model = Intervention
    form_class = InterventionForm
    template_name = 'assets/intervention_form.html'
    success_url = reverse_lazy('assets:intervention_list')

    def form_valid(self, form):
        # Check if status has changed
        old_status = None
        if self.object.pk:
            old_intervention = Intervention.objects.get(pk=self.object.pk)
            old_status = old_intervention.status

        response = super().form_valid(form)

        # If status changed, send notification
        if old_status and old_status != self.object.status:
            try:
                send_intervention_status_update(self.object)
                messages.success(
                    self.request,
                    f'Intervention updated successfully. Status change notification sent to admins.'
                )
            except Exception as e:
                logger.error(f"Failed to send status update notification: {str(e)}")
                messages.success(
                    self.request,
                    'Intervention updated successfully.'
                )
        else:
            messages.success(self.request, 'Intervention updated successfully.')

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['view'] = {'title': f'Edit Intervention: {self.object.title}'}
        return context


class InterventionDeleteView(LoginRequiredMixin, IsAdminMixin, DeleteView):
    model = Intervention
    template_name = 'assets/intervention_confirm_delete.html'
    success_url = reverse_lazy('assets:intervention_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Intervention deleted successfully.')
        return super().delete(request, *args, **kwargs)



