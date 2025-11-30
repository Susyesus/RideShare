from profile_app.supabase_utils import get_supabase_client

def get_user_profile_picture(user):
    supabase = get_supabase_client()

    response = supabase.table('profiles') \
        .select('profile_picture_url') \
        .eq('user_id', user.id) \
        .single() \
        .execute()

    if response.data and response.data.get('profile_picture_url'):
        return response.data['profile_picture_url']

# Utility function to attach driver profile pictures
def attach_driver_profile_pictures(rides):
    """Attach driver profile picture URLs to ride objects."""
    if not rides:
        return rides

    supabase = get_supabase_client()

    # Collect driver IDs
    driver_ids = [ride.driver.id for ride in rides]

    # Fetch all profile picture URLs from Supabase
    response = supabase.table('profiles') \
        .select('user_id, profile_picture_url') \
        .in_('user_id', driver_ids) \
        .execute()

    driver_profiles = {
        str(item['user_id']): item['profile_picture_url']
        for item in (response.data or [])
    }

    # Attach profile picture URL or fallback default
    for ride in rides:
        ride.driver_pic = driver_profiles.get(str(ride.driver.id))

    return rides
