# from django.contrib import admin
# from .models import Job, Category
 
 
# @admin.register(Category)
# class CategoryAdmin(admin.ModelAdmin):
#     list_display  = ['name', 'slug']
#     prepopulated_fields = {'slug': ('name',)}
#     search_fields = ['name']
 
# @admin.register(Job)
# class JobAdmin(admin.ModelAdmin):
#     list_display   = ['title', 'company', 'status', 'job_type',
#                       'experience_level', 'is_featured', 'created_at']
#     list_filter    = ['status', 'job_type', 'experience_level', 'is_featured']
#     search_fields  = ['title', 'company__name']
#     readonly_fields = ['view_count', 'created_at', 'updated_at']
#     list_editable  = ['is_featured', 'status']
 
#     # Admin can feature and change any job status directly from the list
#     actions = ['mark_featured', 'mark_open', 'mark_closed']
 
#     def mark_featured(self, request, queryset):
#         queryset.update(is_featured=True)
#     mark_featured.short_description = 'Mark selected jobs as featured'
 
#     def mark_open(self, request, queryset):
#         queryset.update(status='open')
#     mark_open.short_description = 'Set selected jobs to Open'
 
#     def mark_closed(self, request, queryset):
#         queryset.update(status='closed')
#     mark_closed.short_description = 'Set selected jobs to Closed'
