from app.models.campaign import (
    insert_campaign,
    select_campaigns,
    update_campaign_data,
    delete_campaign_by_id,
)


def create_campaign(data):
    return insert_campaign(data)


def get_campaigns():
    return select_campaigns()


def update_campaign(id, data):
    return update_campaign_data(id, data)


def delete_campaign(id):
    return delete_campaign_by_id(id)
