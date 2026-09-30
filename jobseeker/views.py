import logging
from adrf.views import APIView
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
# from Users.permissions import HasResourcePermission
from django.shortcuts import render
from django.db import DatabaseError, IntegrityError
# from django.contrib.auth.decorators import login_required

from .models import *
from .serializers import *
from .utils import *

logger = logging.getLogger("jobseeker")

class BurstRateThrottle(UserRateThrottle):
    rate = "20/min"

class BaseAPIView(APIView):
    throttle_classes = [AnonRateThrottle, UserRateThrottle, BurstRateThrottle]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        logger.error(f"Unhandled Exception: {str(exc)}")
        return custom_response(False, "Internal server error", errors=str(exc), status_code=500)
    
# @login_required
def jobseeker_dashboard_view(request):
    """
    Renders the frontend HTML dashboard for the Job Seeker.
    """
    return render(request, 'profile.html')

class JobSeekerProfileView(BaseAPIView):
    throttle_classes = [BurstRateThrottle]
    permission_classes = [IsAuthenticated]
    resource = "profile"

    async def get(self, request):
        try:
            logger.info(f"[JobSeekerProfileView GET] Fetching profile for user: {request.user}")
            logger.debug(f"[JobSeekerProfileView GET] Auth token: {request.auth}")

            # Async ORM call
            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[JobSeekerProfileView GET] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            logger.debug(f"[JobSeekerProfileView GET] Profile found (ID: {profile.jobseeker_profile_id}). Serializing data...")
            serializer = JobSeekerProfileSerializer(profile)
            data = await get_serializer_data_from_instance(serializer)
            
            logger.info(f"[JobSeekerProfileView GET] Profile fetched successfully for user: {request.user}")
            return custom_response(True, "Profile fetched", data)

        except DatabaseError as db_err:
            logger.error(f"[JobSeekerProfileView GET] Database error: {str(db_err)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[JobSeekerProfileView GET] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

    async def post(self, request):
        try:
            user = request.user
            logger.info(f"[JobSeekerProfileView POST] Creating Profile for user {user}")
            logger.debug(f"[JobSeekerProfileView POST] Payload: {request.data}")

            # Async ORM call
            profile_exists = await JobSeekerProfile.objects.filter(user=user).aexists()
            if profile_exists:
                logger.warning(f"[JobSeekerProfileView POST] Profile creation rejected - already exists for user: {user}")
                return custom_response(
                    False,
                    "Profile already exists. Use PUT/PATCH to update.",
                    status_code=400
                )

            logger.debug("[JobSeekerProfileView POST] Initializing serializer...")
            serializer = JobSeekerProfileSerializer(data=request.data, context={"request": request})

            is_valid = await validate_serializer(serializer)
            if is_valid:
                logger.debug("[JobSeekerProfileView POST] Validation passed. Saving profile...")
                await save_serializer(serializer, user=user)  # attach logged-in user
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info(f"[JobSeekerProfileView POST] Profile created successfully for user: {user}")
                return custom_response(True, "Profile created", data)

            logger.warning(f"[JobSeekerProfileView POST] Validation failed for user {user}: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as db_err:
            logger.error(f"[JobSeekerProfileView POST] Database error: {str(db_err)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[JobSeekerProfileView POST] Error creating profile: {str(e)}")
            return custom_response(False, "Something went wrong", status_code=500)
    
    async def put(self, request):
        try:
            logger.info(f"[JobSeekerProfileView PUT] Updating profile for user: {request.user}")
            logger.debug(f"[JobSeekerProfileView PUT] Payload: {request.data}")
            
            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[JobSeekerProfileView PUT] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            serializer = JobSeekerProfileSerializer(profile, data=request.data)

            is_valid = await validate_serializer(serializer)
            if is_valid:
                logger.debug(f"[JobSeekerProfileView PUT] Validation passed. Saving updates for profile ID: {profile.jobseeker_profile_id}...")
                await save_serializer(serializer)
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info(f"[JobSeekerProfileView PUT] Profile updated successfully for user: {request.user}")
                return custom_response(True, "Profile updated", data)

            logger.warning(f"[JobSeekerProfileView PUT] Validation failed: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as db_err:
            logger.error(f"[JobSeekerProfileView PUT] Database error: {str(db_err)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[JobSeekerProfileView PUT] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)
    
    async def patch(self, request):
        try:
            logger.info(f"[JobSeekerProfileView PATCH] Partially updating profile for user: {request.user}")
            logger.debug(f"[JobSeekerProfileView PATCH] Payload: {request.data}")
            
            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[JobSeekerProfileView PATCH] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            serializer = JobSeekerProfileSerializer(profile, data=request.data, partial=True)

            is_valid = await validate_serializer(serializer)
            if is_valid:
                logger.debug(f"[JobSeekerProfileView PATCH] Validation passed. Saving partial updates for profile ID: {profile.jobseeker_profile_id}...")
                await save_serializer(serializer)
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info(f"[JobSeekerProfileView PATCH] Profile partially updated successfully for user: {request.user}")
                return custom_response(True, "Profile partially updated", data)

            logger.warning(f"[JobSeekerProfileView PATCH] Validation failed: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as db_err:
            logger.error(f"[JobSeekerProfileView PATCH] Database error: {str(db_err)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[JobSeekerProfileView PATCH] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)


class SkillView(BaseAPIView):
    throttle_classes = [BurstRateThrottle]
    permission_classes = [IsAuthenticated]
    resource = "skill"

    async def get(self, request, skill_id=None):
        try:
            logger.info(f"[SkillView GET] Fetching skills for user: {request.user}, Auth: {request.auth}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[SkillView GET] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            if skill_id:
                logger.debug(f"[SkillView GET] Querying specific skill ID: {skill_id} for profile: {profile.jobseeker_profile_id}")
                skill = await Skill.objects.filter(skill_id=skill_id, profile=profile).afirst()

                if not skill:
                    logger.warning(f"[SkillView GET] Skill not found: {skill_id}")
                    return custom_response(False, "Skill not found", status_code=404)

                serializer = SkillSerializer(skill)
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info(f"[SkillView GET] Specific skill {skill_id} fetched successfully.")
                return custom_response(True, "Skill fetched", data)

            logger.debug(f"[SkillView GET] Querying all skills for profile: {profile.jobseeker_profile_id}")
            # Evaluate queryset safely via our sync_to_async wrapper
            data = await get_serialized_data(SkillSerializer, Skill.objects.filter(profile=profile), many=True)

            logger.info(f"[SkillView GET] List of skills fetched successfully for user: {request.user}")
            return custom_response(True, "Skills list", data)

        except DatabaseError as db_err:
            logger.error(f"[SkillView GET] Database error: {str(db_err)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[SkillView GET] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)
        
    async def post(self, request):
        try:
            logger.info(f"[SkillView POST] Creating skill for user: {request.user}")
            logger.debug(f"[SkillView POST] Payload: {request.data}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[SkillView POST] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            serializer = SkillSerializer(data=request.data, context={"request": request})

            is_valid = await validate_serializer(serializer)
            if is_valid:
                logger.debug("[SkillView POST] Validation passed. Saving skill...")
                await save_serializer(serializer, profile=profile)  
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info(f"[SkillView POST] Skill created successfully for user: {request.user}")
                return custom_response(True, "Skill created", data)

            logger.warning(f"[SkillView POST] Validation failed: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as db_err:
            logger.error(f"[SkillView POST] Database error: {str(db_err)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[SkillView POST] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)
    
    async def delete(self, request, skill_id):
        try:
            logger.info(f"[SkillView DELETE] Deleting skill {skill_id} for user: {request.user}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[SkillView DELETE] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)
            
            logger.debug(f"[SkillView DELETE] Locating skill {skill_id}...")
            skill = await Skill.objects.filter(skill_id=skill_id, profile=profile).afirst()

            if not skill:
                logger.warning(f"[SkillView DELETE] Skill {skill_id} not found or doesn't belong to user.")
                return custom_response(False, "Skill not found", status_code=404)

            logger.debug(f"[SkillView DELETE] Executing database deletion for skill {skill_id}...")
            await skill.adelete()
            
            logger.info(f"[SkillView DELETE] Skill deleted successfully: {skill_id}")
            return custom_response(True, "Skill deleted successfully")

        except DatabaseError as db_err:
            logger.error(f"[SkillView DELETE] Database error: {str(db_err)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[SkillView DELETE] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)


class PreferredLocationView(BaseAPIView):
    throttle_classes = [BurstRateThrottle]
    permission_classes = [IsAuthenticated]
    resource = "location"

    async def get(self, request, location_id=None):
        try:
            logger.info(f"[PreferredLocationView GET] Fetching locations for user: {request.user}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[PreferredLocationView GET] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            if location_id:
                logger.debug(f"[PreferredLocationView GET] Querying location ID: {location_id}")
                location = await PreferredLocation.objects.filter(location_id=location_id, profile=profile).afirst()

                if not location:
                    logger.warning(f"[PreferredLocationView GET] Location not found: {location_id}")
                    return custom_response(False, "Location not found", status_code=404)

                serializer = PreferredLocationSerializer(location, context={"request": request})
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info(f"[PreferredLocationView GET] Single location {location_id} fetched.")
                return custom_response(True, "Location fetched", data)

            logger.debug(f"[PreferredLocationView GET] Querying all locations for profile: {profile.jobseeker_profile_id}")
            data = await get_serialized_data(
                PreferredLocationSerializer, 
                PreferredLocation.objects.filter(profile=profile), 
                many=True, 
                context={"request": request}
            )

            logger.info("[PreferredLocationView GET] Locations list fetched successfully.")
            return custom_response(True, "Locations list", data)

        except DatabaseError as e:
            logger.error(f"[PreferredLocationView GET] Database error: {str(e)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[PreferredLocationView GET] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

    async def post(self, request):
        try:
            logger.info(f"[PreferredLocationView POST] Creating location for user: {request.user}")
            logger.debug(f"[PreferredLocationView POST] Payload: {request.data}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[PreferredLocationView POST] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            serializer = PreferredLocationSerializer(data=request.data, context={"request": request})

            is_valid = await validate_serializer(serializer)
            if is_valid:
                logger.debug("[PreferredLocationView POST] Validation passed. Saving location...")
                await save_serializer(serializer, profile=profile) 
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info("[PreferredLocationView POST] Location created successfully.")
                return custom_response(True, "Location created", data)

            logger.warning(f"[PreferredLocationView POST] Validation failed: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except IntegrityError as e:
            logger.error(f"[PreferredLocationView POST] Integrity error: {str(e)}", exc_info=True)
            return custom_response(False, "Integrity error", status_code=400)
        except DatabaseError as db_err:
            logger.error(f"[PreferredLocationView POST] Database error: {str(db_err)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[PreferredLocationView POST] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)
    
    async def delete(self, request, location_id):
        try:
            logger.warning(f"[PreferredLocationView DELETE] Deleting Location {location_id} for user: {request.user}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[PreferredLocationView DELETE] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            logger.debug(f"[PreferredLocationView DELETE] Finding location {location_id}...")
            location = await PreferredLocation.objects.filter(location_id=location_id, profile=profile).afirst()

            if not location:
                logger.warning(f"[PreferredLocationView DELETE] Location {location_id} not found.")
                return custom_response(False, "Location not found", status_code=404)

            logger.debug(f"[PreferredLocationView DELETE] Executing database deletion for location {location_id}...")
            await location.adelete()

            logger.info(f"[PreferredLocationView DELETE] Location deleted successfully: {location_id}")
            return custom_response(True, "Location deleted successfully")

        except DatabaseError as e:
            logger.error(f"[PreferredLocationView DELETE] Database error: {str(e)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[PreferredLocationView DELETE] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)


class EducationView(BaseAPIView):
    throttle_classes = [BurstRateThrottle]
    permission_classes = [IsAuthenticated]
    resource = "education"

    async def get(self, request, education_id=None):
        try:
            logger.info(f"[EducationView GET] Fetching Education for user: {request.user}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[EducationView GET] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            if education_id:
                logger.debug(f"[EducationView GET] Querying education ID: {education_id}")
                education = await Education.objects.filter(education_id=education_id, profile=profile).afirst()

                if not education:
                    logger.warning(f"[EducationView GET] Education not found: {education_id}")
                    return custom_response(False, "Education not found", status_code=404)

                serializer = EducationSerializer(education, context={"request": request})
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info(f"[EducationView GET] Education {education_id} fetched successfully.")
                return custom_response(True, "Education fetched", data)

            logger.debug(f"[EducationView GET] Querying all education records for profile: {profile.jobseeker_profile_id}")
            data = await get_serialized_data(
                EducationSerializer,
                Education.objects.filter(profile=profile),
                many=True,
                context={"request": request}
            )

            logger.info("[EducationView GET] Education list fetched successfully.")
            return custom_response(True, "Education list", data)

        except DatabaseError as e:
            logger.error(f"[EducationView GET] Database error: {str(e)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[EducationView GET] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)
        
    async def post(self, request):
        try:
            logger.info(f"[EducationView POST] Creating Education for user: {request.user}")
            logger.debug(f"[EducationView POST] Payload: {request.data}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[EducationView POST] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            serializer = EducationSerializer(data=request.data, context={"request": request})

            is_valid = await validate_serializer(serializer)
            if is_valid:
                logger.debug("[EducationView POST] Validation passed. Saving education record...")
                await save_serializer(serializer, profile=profile)
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info("[EducationView POST] Education created successfully.")
                return custom_response(True, "Education created", data)

            logger.warning(f"[EducationView POST] Validation failed: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except IntegrityError as e:
            logger.error(f"[EducationView POST] Integrity error: {str(e)}", exc_info=True)
            return custom_response(False, "Integrity error", status_code=400)
        except Exception as e:
            logger.exception(f"[EducationView POST] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

    async def put(self, request, education_id):
        try:
            logger.info(f"[EducationView PUT] Updating Education {education_id} for user: {request.user}")
            logger.debug(f"[EducationView PUT] Payload: {request.data}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[EducationView PUT] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            education = await Education.objects.filter(education_id=education_id, profile=profile).afirst()

            if not education:
                logger.warning(f"[EducationView PUT] Education {education_id} not found.")
                return custom_response(False, "Education not found", status_code=404)

            serializer = EducationSerializer(education, data=request.data, context={"request": request})

            is_valid = await validate_serializer(serializer)
            if is_valid:
                logger.debug(f"[EducationView PUT] Validation passed. Updating education {education_id}...")
                await save_serializer(serializer)
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info(f"[EducationView PUT] Education {education_id} updated successfully.")
                return custom_response(True, "Education updated", data)

            logger.warning(f"[EducationView PUT] Validation failed: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as e:
            logger.error(f"[EducationView PUT] Database error: {str(e)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[EducationView PUT] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

    async def patch(self, request, education_id):
        try:
            logger.info(f"[EducationView PATCH] Partially updating Education {education_id} for user: {request.user}")
            logger.debug(f"[EducationView PATCH] Payload: {request.data}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[EducationView PATCH] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            education = await Education.objects.filter(education_id=education_id, profile=profile).afirst()

            if not education:
                logger.warning(f"[EducationView PATCH] Education {education_id} not found.")
                return custom_response(False, "Education not found", status_code=404)

            serializer = EducationSerializer(
                education, data=request.data, partial=True, context={"request": request}
            )

            is_valid = await validate_serializer(serializer)
            if is_valid:
                logger.debug(f"[EducationView PATCH] Validation passed. Saving partial updates for {education_id}...")
                await save_serializer(serializer)
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info(f"[EducationView PATCH] Education {education_id} partially updated successfully.")
                return custom_response(True, "Education partially updated", data)

            logger.warning(f"[EducationView PATCH] Validation failed: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except Exception as e:
            logger.exception(f"[EducationView PATCH] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

    async def delete(self, request, education_id):
        try:
            logger.warning(f"[EducationView DELETE] Deleting Education {education_id} for user: {request.user}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[EducationView DELETE] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            education = await Education.objects.filter(education_id=education_id, profile=profile).afirst()

            if not education:
                logger.warning(f"[EducationView DELETE] Education {education_id} not found.")
                return custom_response(False, "Education not found", status_code=404)

            logger.debug(f"[EducationView DELETE] Executing database deletion for {education_id}...")
            await education.adelete()

            logger.info(f"[EducationView DELETE] Education {education_id} deleted successfully.")
            return custom_response(True, "Education deleted successfully")

        except DatabaseError as e:
            logger.error(f"[EducationView DELETE] Database error: {str(e)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[EducationView DELETE] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)


class ExperienceView(BaseAPIView):
    throttle_classes = [BurstRateThrottle]
    permission_classes = [IsAuthenticated]
    resource = "experience"
    
    async def get(self, request, experience_id=None):
        try:
            logger.info(f"[ExperienceView GET] Fetching Experience for user: {request.user}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[ExperienceView GET] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            if experience_id:
                logger.debug(f"[ExperienceView GET] Querying specific experience ID: {experience_id}")
                experience = await Experience.objects.filter(experience_id=experience_id, profile=profile).afirst()

                if not experience:
                    logger.warning(f"[ExperienceView GET] Experience {experience_id} not found.")
                    return custom_response(False, "Experience not found", status_code=404)

                serializer = ExperienceSerializer(experience)
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info(f"[ExperienceView GET] Experience {experience_id} fetched successfully.")
                return custom_response(True, "Experience fetched", data)

            logger.debug(f"[ExperienceView GET] Querying all experience records for profile: {profile.jobseeker_profile_id}")
            data = await get_serialized_data(
                ExperienceSerializer,
                Experience.objects.filter(profile=profile),
                many=True
            )

            logger.info("[ExperienceView GET] Experience list fetched successfully.")
            return custom_response(True, "Experience list", data)

        except DatabaseError as e:
            logger.error(f"[ExperienceView GET] Database error: {str(e)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[ExperienceView GET] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", status_code=500)

    async def post(self, request):
        try:
            logger.info(f"[ExperienceView POST] Creating Experience for user: {request.user}")
            logger.debug(f"[ExperienceView POST] Payload: {request.data}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[ExperienceView POST] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            serializer = ExperienceSerializer(data=request.data, context={"request": request})

            is_valid = await validate_serializer(serializer)
            if is_valid:
                logger.debug("[ExperienceView POST] Validation passed. Saving experience record...")
                await save_serializer(serializer, profile=profile)
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info("[ExperienceView POST] Experience created successfully.")
                return custom_response(True, "Experience created", data)

            logger.warning(f"[ExperienceView POST] Validation failed: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as e:
            logger.error(f"[ExperienceView POST] Database error: {str(e)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[ExperienceView POST] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", status_code=500)
        
    async def put(self, request, experience_id):
        try:
            logger.info(f"[ExperienceView PUT] Updating Experience {experience_id} for user: {request.user}")
            logger.debug(f"[ExperienceView PUT] Payload: {request.data}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[ExperienceView PUT] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            experience = await Experience.objects.filter(experience_id=experience_id, profile=profile).afirst()

            if not experience:
                logger.warning(f"[ExperienceView PUT] Experience {experience_id} not found.")
                return custom_response(False, "Experience not found", status_code=404)

            serializer = ExperienceSerializer(experience, data=request.data, partial=False)

            is_valid = await validate_serializer(serializer)
            if is_valid:
                logger.debug(f"[ExperienceView PUT] Validation passed. Saving updates for {experience_id}...")
                await save_serializer(serializer)
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info(f"[ExperienceView PUT] Experience {experience_id} updated successfully.")
                return custom_response(True, "Experience updated", data)

            logger.warning(f"[ExperienceView PUT] Validation failed: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as e:
            logger.error(f"[ExperienceView PUT] Database error: {str(e)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[ExperienceView PUT] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", status_code=500)

    async def patch(self, request, experience_id):
        try:
            logger.info(f"[ExperienceView PATCH] Partially updating Experience {experience_id} for user: {request.user}")
            logger.debug(f"[ExperienceView PATCH] Payload: {request.data}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[ExperienceView PATCH] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            experience = await Experience.objects.filter(experience_id=experience_id, profile=profile).afirst()

            if not experience:
                logger.warning(f"[ExperienceView PATCH] Experience {experience_id} not found.")
                return custom_response(False, "Experience not found", status_code=404)

            serializer = ExperienceSerializer(experience, data=request.data, partial=True)

            is_valid = await validate_serializer(serializer)
            if is_valid:
                logger.debug(f"[ExperienceView PATCH] Validation passed. Saving partial updates for {experience_id}...")
                await save_serializer(serializer)
                data = await get_serializer_data_from_instance(serializer)
                
                logger.info(f"[ExperienceView PATCH] Experience {experience_id} partially updated successfully.")
                return custom_response(True, "Experience partially updated", data)

            logger.warning(f"[ExperienceView PATCH] Validation failed: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as e:
            logger.error(f"[ExperienceView PATCH] Database error: {str(e)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[ExperienceView PATCH] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", status_code=500)

    async def delete(self, request, experience_id):
        try:
            logger.warning(f"[ExperienceView DELETE] Deleting Experience {experience_id} for user: {request.user}")

            profile = await JobSeekerProfile.objects.filter(user=request.user).afirst()

            if not profile:
                logger.warning(f"[ExperienceView DELETE] Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            experience = await Experience.objects.filter(experience_id=experience_id, profile=profile).afirst()

            if not experience:
                logger.warning(f"[ExperienceView DELETE] Experience {experience_id} not found.")
                return custom_response(False, "Experience not found", status_code=404)

            logger.debug(f"[ExperienceView DELETE] Executing database deletion for {experience_id}...")
            await experience.adelete()
            
            logger.info(f"[ExperienceView DELETE] Experience {experience_id} deleted successfully.")
            return custom_response(True, "Experience deleted successfully")

        except DatabaseError as e:
            logger.error(f"[ExperienceView DELETE] Database error: {str(e)}", exc_info=True)
            return custom_response(False, "Database error", status_code=500)
        except Exception as e:
            logger.exception(f"[ExperienceView DELETE] Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", status_code=500)