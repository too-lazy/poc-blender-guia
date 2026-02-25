class PatientsController < ApplicationController
  before_action :set_patient, only: %i[show edit update destroy]

  def index
    @patients = Patient.all.order(created_at: :desc)
  end

  def show
    @cases = @patient.cases.order(created_at: :desc)
  end

  def new
    @patient = Patient.new
  end

  def create
    @patient = Patient.new(patient_params)
    if @patient.save
      redirect_to @patient, notice: "Patient created."
    else
      render :new, status: :unprocessable_entity
    end
  end

  def edit; end

  def update
    if @patient.update(patient_params)
      redirect_to @patient, notice: "Patient updated."
    else
      render :edit, status: :unprocessable_entity
    end
  end

  def destroy
    @patient.destroy
    redirect_to patients_path, notice: "Patient deleted."
  end

  private

  def set_patient
    @patient = Patient.find(params[:id])
  end

  def patient_params
    params.expect(patient: [ :name, :email, :notes ])
  end
end
