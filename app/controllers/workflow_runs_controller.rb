class WorkflowRunsController < ApplicationController
  before_action :set_run

  def show
  end

  def place_screws
  end

  def save_screws
    raw = params.permit(screws: {}).to_h[:screws] || {}
    positions = raw.values.map { |s| s.slice("x", "y", "z", "angle_x", "angle_y", "angle_z").transform_values(&:to_f) }
    @case.update!(screw_positions: positions)

    if @case.screw_positions.present?
      guide_run = nil
      ActiveRecord::Base.transaction do
        guide_run = @case.workflow_runs.create!(status: "pending")
        @case.update!(status: "processing")
      end
      GuideGenerationJob.perform_later(guide_run.id)
      redirect_to workflow_run_path(guide_run), notice: "#{positions.size} tornillos guardados. Generando guía quirúrgica..."
    else
      redirect_to place_screws_workflow_run_path(@run), alert: "Coloca al menos un tornillo."
    end
  end

  private

  def set_run
    if params[:patient_id]
      @patient = Patient.find(params[:patient_id])
      @case = @patient.cases.find(params[:case_id])
      @run = @case.workflow_runs.find(params[:id])
    else
      @run = WorkflowRun.find(params[:id])
      @case = @run.case
      @patient = @case.patient
    end
  end
end
