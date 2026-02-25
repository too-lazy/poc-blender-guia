class WorkflowRun < ApplicationRecord
  belongs_to :case
  has_one_attached :render_output

  validates :status, inclusion: { in: %w[pending running completed failed] }

  def duration
    return nil unless started_at && completed_at
    completed_at - started_at
  end
end
