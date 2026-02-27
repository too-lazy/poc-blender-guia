class BlenderWorkflowJob < ApplicationJob
  queue_as :default

  BLENDER_SCRIPT = Rails.root.join("src", "cli.py").to_s

  def perform(workflow_run_id)
    run = WorkflowRun.find(workflow_run_id)
    dental_case = run.case
    run.update!(status: "running", started_at: Time.current)

    Dir.mktmpdir("blender_workflow") do |tmpdir|
      upper_path = File.join(tmpdir, "upper.stl")
      lower_path = File.join(tmpdir, "lower.stl")
      output_path = File.join(tmpdir, "render.png")

      # Download STL arches from Active Storage
      download_attachment(dental_case.upper_arch_file, upper_path)
      download_attachment(dental_case.lower_arch_file, lower_path)

      # Build Blender command
      cmd = [
        "blender", "--background", "--python", BLENDER_SCRIPT,
        "--", "--upper", upper_path, "--lower", lower_path
      ]

      # Extract DICOM zip if attached
      if dental_case.dicom_zip_file.attached?
        dicom_dir = extract_dicom_zip(dental_case, tmpdir)
        cmd += [ "--dicom-dir", dicom_dir ] if dicom_dir
      end

      cmd << output_path

      log_output = []
      IO.popen(cmd, err: [ :child, :out ]) do |io|
        io.each_line { |line| log_output << line }
      end

      if $?.success? && File.exist?(output_path)
        run.render_output.attach(
          io: File.open(output_path),
          filename: "render_#{run.id}.png",
          content_type: "image/png"
        )
        run.update!(
          status: "completed",
          completed_at: Time.current,
          log_output: log_output.join
        )
        dental_case.update!(status: "completed")
        # Purge DICOM zip from Active Storage — large file only needed during processing
        dental_case.dicom_zip_file.purge if dental_case.dicom_zip_file.attached?
      else
        run.update!(
          status: "failed",
          completed_at: Time.current,
          error_message: "Blender exited with code #{$?.exitstatus}",
          log_output: log_output.join
        )
        dental_case.update!(status: "failed")
      end
    end
  rescue => e
    run = WorkflowRun.find_by(id: workflow_run_id)
    if run
      run.update!(
        status: "failed",
        completed_at: Time.current,
        error_message: e.message,
        log_output: e.backtrace&.first(20)&.join("\n")
      )
      run.case.update!(status: "failed")
    end
    raise
  end

  private

  def download_attachment(attachment, dest_path)
    File.open(dest_path, "wb") do |f|
      attachment.download { |chunk| f.write(chunk) }
    end
  end

  def extract_dicom_zip(dental_case, tmpdir)
    zip_path = File.join(tmpdir, "dicom.zip")
    download_attachment(dental_case.dicom_zip_file, zip_path)

    dicom_dir = File.join(tmpdir, "dicom")
    FileUtils.mkdir_p(dicom_dir)

    # Extract zip
    unless system("unzip", "-q", zip_path, "-d", dicom_dir)
      raise "Failed to extract DICOM zip (exit code: #{$?.exitstatus})"
    end

    # Find the directory with the most files (CTVolume series)
    find_ctvolume_dir(dicom_dir)
  end

  def find_ctvolume_dir(root_dir)
    best_dir = root_dir
    best_count = 0

    Dir.glob(File.join(root_dir, "**", "*")).select { |f| File.file?(f) }
       .group_by { |f| File.dirname(f) }
       .each do |dir, files|
      if files.size > best_count
        best_count = files.size
        best_dir = dir
      end
    end

    best_dir
  end
end
