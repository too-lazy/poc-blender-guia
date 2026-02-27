class QuickProcessesController < ApplicationController
  def new
    @case = Case.new
    @patients = Patient.order(:name)
  end

  def create
    @case = Case.new(case_params)
    @case.description = "Quick process" if @case.description.blank?

    if @case.save
      if @case.upper_arch_file.attached? && @case.lower_arch_file.attached? && @case.dicom_zip_file.attached?
        run = nil
        ActiveRecord::Base.transaction do
          run = @case.workflow_runs.create!(status: "pending")
          @case.update!(status: "processing")
        end
        BlenderWorkflowJob.perform_later(run.id)
        redirect_to quick_process_path, notice: "Workflow started! Processing your files."
      else
        missing = []
        missing << "upper arch STL" unless @case.upper_arch_file.attached?
        missing << "lower arch STL" unless @case.lower_arch_file.attached?
        missing << "DICOM zip" unless @case.dicom_zip_file.attached?
        redirect_to quick_process_path, alert: "Please upload: #{missing.join(', ')}."
      end
    else
      render :new, status: :unprocessable_entity
    end
  end

  def show
    @recent_runs = WorkflowRun.includes(case: :patient, render_output_attachment: :blob)
                               .order(created_at: :desc)
                               .limit(20)
  end

  private

  def case_params
    params.expect(case: [ :description, :patient_id, :upper_arch_file, :lower_arch_file, :dicom_zip_file ])
  end
end
