from flask import Blueprint, request
from app.services.campaign_service import (
    create_campaign, get_campaigns, update_campaign, delete_campaign
)

campaign = Blueprint('campaign', __name__)

@campaign.route('/campaigns', methods=['POST'])
def create():
    return create_campaign(request.json)

@campaign.route('/campaigns', methods=['GET'])
def read():
    return get_campaigns()

@campaign.route('/campaigns/<int:id>', methods=['PUT'])
def update(id):
    return update_campaign(id, request.json)

@campaign.route('/campaigns/<int:id>', methods=['DELETE'])
def delete(id):
    return delete_campaign(id)
