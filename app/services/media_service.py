from app.models.media import insert_media, select_media_by_campaign


def add_media(campaign_id, data):
    return insert_media(campaign_id, data)


def get_media_by_campaign(campaign_id):
    return select_media_by_campaign(campaign_id)
