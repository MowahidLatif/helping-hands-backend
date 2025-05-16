from app.models.donation import (
    insert_donation, select_donations_by_campaign
)

def create_donation(data):
    return insert_donation(data)

def get_donations_for_campaign(campaign_id):
    return select_donations_by_campaign(campaign_id)
