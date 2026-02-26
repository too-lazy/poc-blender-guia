class QuickProcessesController < ApplicationController
  def new
    @case = Case.new
  end

  def create
    @case = Case.new(case_params)
    @case.description = "Quick process" if @case.description.blank?

    if @case.save
      if @case.stl_file.attached?
        run = @case.workflow_runs.create!(status: "pending")
        @case.update!(status: "processing")
        BlenderWorkflowJob.perform_later(run.id)
        redirect_to quick_process_path, notice: "Workflow started! Processing your STL file."
      else
        redirect_to quick_process_path, alert: "Please upload an STL file."
      end
    else
      render :new, status: :unprocessable_entity
    end
  end

  def show
    @recent_runs = WorkflowRun.includes(:case, render_output_attachment: :blob)
                               .joins(:case)
                               .where(cases: { patient_id: nil })
                               .order(created_at: :desc)
                               .limit(20)
  end

  private

  def case_params
    params.expect(case: [ :description, :stl_file, :radiograph_file, :landmarks_file ])
  end
end
