# detect.py
    img = cv2.cvtColor(img_raw.numpy(), cv2.COLOR_RGB2BGR)
    cv2.imwrite(FLAGS.output, img)
