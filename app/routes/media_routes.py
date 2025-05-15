from flask import Blueprint, request
from app.services.media_service import (
    add_media, get_media_by_campaign
)

media = Blueprint('media', __name__)

@media.route('/campaigns/<int:campaign_id>/media', methods=['POST'])
def upload():
    return add_media(campaign_id=request.view_args['campaign_id'], data=request.json)

@media.route('/campaigns/<int:campaign_id>/media', methods=['GET'])
def fetch_media(campaign_id):
    return get_media_by_campaign(campaign_id)
