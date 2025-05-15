from flask import Blueprint, request
from app.services.donation_service import (
    create_donation, get_donations_for_campaign
)

donation = Blueprint('donation', __name__)

@donation.route('/donations', methods=['POST'])
def donate():
    return create_donation(request.json)

@donation.route('/campaigns/<int:campaign_id>/donations', methods=['GET'])
def list_donations(campaign_id):
    return get_donations_for_campaign(campaign_id)
