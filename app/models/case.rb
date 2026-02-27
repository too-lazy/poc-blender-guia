class Case < ApplicationRecord
  belongs_to :patient, optional: true
  has_many :workflow_runs, dependent: :destroy
  has_one_attached :stl_file
  has_one_attached :radiograph_file
  has_one_attached :landmarks_file
  has_one_attached :upper_arch_file
  has_one_attached :lower_arch_file
  has_one_attached :dicom_zip_file
  has_one_attached :guide_stl_file

  validates :description, presence: true
  validates :status, inclusion: { in: %w[pending processing completed failed] }

  def latest_run
    workflow_runs.order(created_at: :desc).first
  end
end
