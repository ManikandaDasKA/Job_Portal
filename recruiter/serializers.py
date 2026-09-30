from rest_framework import serializers
from .models import Company, Recruiter
from jobseeker.validators import phone_validator

class CompanySerializer(serializers.ModelSerializer):
    # 1. Add the custom method field here
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'company_id',
            'created_by',
            'name',
            'description',
            'website',
            'location',
            'address',
            'industry',
            'is_verified',
            'created_at',
            'updated_at',
            'is_admin',  # 2. Add it to the fields list so it gets returned to the frontend
        ]

        read_only_fields = [
            'company_id',
            'created_at',
            'updated_at',
            'created_by',
            'is_verified',
            'is_admin'   # 3. Method fields are read-only by default, but it's good practice to list it here
        ]

    # 4. Add the getter method to evaluate the user's permissions
    def get_is_admin(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            # Check if this user has an admin recruiter profile for this company
            return Recruiter.objects.filter(
                company=obj, 
                user=request.user, 
                # is_admin=True, 
                have_access=True
            ).exists()
        return False

    def validate(self, data):

        if self.instance is None:

            required_fields = [
                'name',
                'location'
            ]

            missing = [
                field for field in required_fields
                if not data.get(field)
            ]

            if missing:
                raise serializers.ValidationError({
                    "error": f"Missing required fields: {', '.join(missing)}"
                })

        name = data.get("name", None)

        if name is not None:

            queryset = Company.objects.filter(
                name__iexact=name
            )

            if self.instance:
                queryset = queryset.exclude(
                    pk=self.instance.pk
                )

            if queryset.exists():
                raise serializers.ValidationError({
                    "name": "Company name already exists"
                })

        website = data.get("website", None)

        if website is not None:

            queryset = Company.objects.filter(
                website=website
            )

            if self.instance:
                queryset = queryset.exclude(
                    pk=self.instance.pk
                )

            if queryset.exists():
                raise serializers.ValidationError({
                    "website": "This website already exists"
                })

        return data
    

class RecruiterSerializer(serializers.ModelSerializer):

    company_details = CompanySerializer(
        source='company',
        read_only=True
    )

    phone_number = serializers.CharField(
        validators=[phone_validator],
        required=True
    )

    class Meta:
        model = Recruiter
        fields = [
            'recruiter_id',
            'user',
            'company',
            'full_name',
            'designation',
            'phone_number',
            'gender',
            'created_at',
            'updated_at',
            'company_details' # Added to fields to ensure the nested serializer is outputted
        ]

        read_only_fields = [
            'recruiter_id',
            'user',
            'company',
            'created_at',
            'updated_at'
        ]

    def validate(self, data):

        if self.instance is None:

            required_fields = [
                'company',
                'full_name',
                'designation',
                'phone_number'
            ]

            missing = [
                field for field in required_fields
                if not data.get(field)
            ]

            if missing:
                raise serializers.ValidationError({
                    "error": f"Missing required fields: {', '.join(missing)}"
                })

        phone = data.get("phone_number", None)

        if phone is not None:

            queryset = Recruiter.objects.filter(
                phone_number=phone
            )

            if self.instance:
                queryset = queryset.exclude(
                    pk=self.instance.pk
                )

            if queryset.exists():
                raise serializers.ValidationError({
                    "phone_number": "This phone number already exists"
                })

        return data

    # Domain validation block removed/commented out based on your provided snippet
    
 # domain = data.get("domain", None)

        # if domain is not None:

        #     domain = domain.strip().lower()

        #     domain_pattern = r'^[a-z0-9.-]+\.[a-z]{2,}$'

        #     if not re.match(domain_pattern, domain):
        #         raise serializers.ValidationError({
        #             "domain": "Enter a valid domain name"
        #         })

        #     queryset = Company.objects.filter(
        #         domain__iexact=domain
        #     )

        #     if self.instance:
        #         queryset = queryset.exclude(
        #             pk=self.instance.pk
        #         )

        #     if queryset.exists():
        #         raise serializers.ValidationError({
        #             "domain": "This domain already exists"
        #         })

        #     data["domain"] = domain
