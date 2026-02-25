class CasesController < ApplicationController
  before_action :set_patient
  before_action :set_case, only: %i[show edit update destroy execute_workflow]

  def new
    @case = @patient.cases.build
  end

  def create
    @case = @patient.cases.build(case_params)
    if @case.save
      redirect_to patient_case_path(@patient, @case), notice: "Case created."
    else
      render :new, status: :unprocessable_entity
    end
  end

  def show
    @workflow_runs = @case.workflow_runs.order(created_at: :desc)
  end

  def edit; end

  def update
    if @case.update(case_params)
      redirect_to patient_case_path(@patient, @case), notice: "Case updated."
    else
      render :edit, status: :unprocessable_entity
    end
  end

  def destroy
    @case.destroy
    redirect_to patient_path(@patient), notice: "Case deleted."
  end

  def execute_workflow
    unless @case.stl_file.attached?
      redirect_to patient_case_path(@patient, @case), alert: "Upload an STL file first."
      return
    end

    run = @case.workflow_runs.create!(status: "pending")
    @case.update!(status: "processing")
    BlenderWorkflowJob.perform_later(run.id)
    redirect_to patient_case_path(@patient, @case), notice: "Workflow started."
  end

  private

  def set_patient
    @patient = Patient.find(params[:patient_id])
  end

  def set_case
    @case = @patient.cases.find(params[:id])
  end

  def case_params
    params.expect(case: [ :description, :stl_file ])
  end
end
