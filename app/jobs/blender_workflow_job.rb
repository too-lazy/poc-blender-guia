class BlenderWorkflowJob < ApplicationJob
  queue_as :default

  BLENDER_SCRIPT = Rails.root.join("src", "cli.py").to_s

  def perform(workflow_run_id)
    run = WorkflowRun.find(workflow_run_id)
    dental_case = run.case
    run.update!(status: "running", started_at: Time.current)

    Dir.mktmpdir("blender_workflow") do |tmpdir|
      input_path = File.join(tmpdir, "input.stl")
      output_path = File.join(tmpdir, "render.png")

      # Download STL from Active Storage to temp file
      File.open(input_path, "wb") do |f|
        dental_case.stl_file.download { |chunk| f.write(chunk) }
      end

      # Execute Blender pipeline
      cmd = [
        "blender", "--background", "--python", BLENDER_SCRIPT,
        "--", input_path, output_path
      ]

      # Add radiograph if attached
      if dental_case.radiograph_file.attached?
        ext = File.extname(dental_case.radiograph_file.filename.to_s).presence || ".png"
        radio_path = File.join(tmpdir, "radiograph#{ext}")
        File.open(radio_path, "wb") do |f|
          dental_case.radiograph_file.download { |chunk| f.write(chunk) }
        end
        cmd += [ "--radiograph", radio_path ]

        # Add landmarks if attached
        if dental_case.landmarks_file.attached?
          landmarks_path = File.join(tmpdir, "landmarks.json")
          File.open(landmarks_path, "wb") do |f|
            dental_case.landmarks_file.download { |chunk| f.write(chunk) }
          end
          cmd += [ "--landmarks", landmarks_path ]
        end
      end

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
end
