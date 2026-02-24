// Types
export interface Playbook {
    id: number;
    name: string;
    description: string | null;
    creator_id: number;
    created_at: string;
    updated_at: string;
}

export interface PlaybookMember {
    user_id: number;
    added_by: number;
    added_at: string;
    email?: string;
    role?: string;
}

export interface PlaybookModel {
    model_id: number;
    added_by: number;
    added_at: string;
    model_name?: string;
    model_version?: number;
    project_id?: number;
    project_name?: string;
    newer_version_available: boolean;
}

export interface CampaignFormField {
    field_name: string;
    label: string;
    field_type: string;
    required: boolean;
    placeholder?: string;
    options?: string[];
    default_value?: string;
    validation_regex?: string;
    help_text?: string;
}

export interface PlaybookCampaignForm {
    id: number;
    playbook_id: number;
    fields: CampaignFormField[];
    created_by: number;
    created_at: string;
    updated_at: string;
}

export interface PlaybookDetail extends Playbook {
    team_members: PlaybookMember[];
    models: PlaybookModel[];
    campaign_form: PlaybookCampaignForm | null;
}

export interface PlaybookCreate {
    name: string;
    description?: string;
}

export interface PlaybookUpdate {
    name?: string;
    description?: string;
}